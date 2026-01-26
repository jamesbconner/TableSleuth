"""Forensic analysis services for Delta Lake tables.

This module provides static methods for analyzing Delta Lake tables to identify
optimization opportunities, storage waste, and operational inefficiencies.
"""

from __future__ import annotations

import logging
import statistics
import time
from pathlib import Path
from typing import Any

from deltalake import DeltaTable

from tablesleuth.models import SnapshotInfo

from .formats.delta_filesystem import DeltaLogFileSystem
from .formats.delta_log_parser import AddAction, DeltaLogParser

try:
    from pyarrow import fs as pafs
except ImportError:
    pafs = None

logger = logging.getLogger(__name__)


class DeltaForensics:
    """Forensic analysis services for Delta tables.

    Provides static methods for analyzing Delta Lake tables including:
    - File size distribution analysis
    - Storage waste analysis
    - DML operation impact analysis
    - Z-order effectiveness analysis
    - Checkpoint health monitoring
    - Optimization recommendations
    """

    @staticmethod
    def analyze_file_sizes(snapshot: SnapshotInfo) -> dict[str, Any]:
        """Analyze file size distribution for a Delta table snapshot.

        Calculates comprehensive file size statistics including distribution
        histogram, small file detection, and optimization opportunities.

        Args:
            snapshot: SnapshotInfo containing data files to analyze

        Returns:
            Dictionary containing:
            - histogram: File size distribution buckets with counts
                - "< 1MB": count of files smaller than 1MB
                - "1-10MB": count of files between 1MB and 10MB
                - "10-100MB": count of files between 10MB and 100MB
                - "> 100MB": count of files larger than 100MB
            - small_file_count: Number of files smaller than 10MB
            - small_file_percentage: Percentage of files that are small (0-100)
            - optimization_opportunity: Estimated file count reduction from OPTIMIZE
            - min_size_bytes: Minimum file size in bytes
            - max_size_bytes: Maximum file size in bytes
            - median_size_bytes: Median file size in bytes
            - total_size_bytes: Total size of all files in bytes
            - total_file_count: Total number of files

        Examples:
            >>> snapshot = SnapshotInfo(...)
            >>> analysis = DeltaForensics.analyze_file_sizes(snapshot)
            >>> print(f"Small files: {analysis['small_file_count']}")
            >>> print(f"Optimization opportunity: {analysis['optimization_opportunity']} files")
        """
        # Extract file sizes from data files
        file_sizes = [file.file_size_bytes for file in snapshot.data_files]

        # Handle empty snapshot
        if not file_sizes:
            return {
                "histogram": {
                    "< 1MB": 0,
                    "1-10MB": 0,
                    "10-100MB": 0,
                    "> 100MB": 0,
                },
                "small_file_count": 0,
                "small_file_percentage": 0.0,
                "optimization_opportunity": 0,
                "min_size_bytes": 0,
                "max_size_bytes": 0,
                "median_size_bytes": 0,
                "total_size_bytes": 0,
                "total_file_count": 0,
            }

        # Define size thresholds in bytes
        MB = 1024 * 1024
        SIZE_1MB = 1 * MB
        SIZE_10MB = 10 * MB
        SIZE_100MB = 100 * MB

        # Calculate histogram buckets
        histogram = {
            "< 1MB": sum(1 for size in file_sizes if size < SIZE_1MB),
            "1-10MB": sum(1 for size in file_sizes if SIZE_1MB <= size < SIZE_10MB),
            "10-100MB": sum(1 for size in file_sizes if SIZE_10MB <= size < SIZE_100MB),
            "> 100MB": sum(1 for size in file_sizes if size >= SIZE_100MB),
        }

        # Calculate small file statistics
        small_file_count = sum(1 for size in file_sizes if size < SIZE_10MB)
        total_file_count = len(file_sizes)
        small_file_percentage = (small_file_count / total_file_count) * 100.0

        # Estimate optimization opportunity
        # OPTIMIZE typically combines small files into larger files
        # Conservative estimate: reduce small files by 80% (combine 5 small files into 1)
        # Only count files < 10MB as candidates for optimization
        optimization_opportunity = int(small_file_count * 0.8) if small_file_count > 0 else 0

        # Calculate size statistics
        min_size_bytes = min(file_sizes)
        max_size_bytes = max(file_sizes)
        median_size_bytes = int(statistics.median(file_sizes))
        total_size_bytes = sum(file_sizes)

        return {
            "histogram": histogram,
            "small_file_count": small_file_count,
            "small_file_percentage": round(small_file_percentage, 2),
            "optimization_opportunity": optimization_opportunity,
            "min_size_bytes": min_size_bytes,
            "max_size_bytes": max_size_bytes,
            "median_size_bytes": median_size_bytes,
            "total_size_bytes": total_size_bytes,
            "total_file_count": total_file_count,
        }

    @staticmethod
    def analyze_storage_waste(
        table: DeltaTable,
        current_version: int,
        retention_hours: int = 168,  # 7 days default
        storage_options: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Analyze storage waste from tombstoned files.

        Identifies files that have been removed (tombstoned) but not yet vacuumed,
        calculates storage waste, and determines reclaimable storage based on
        retention period.

        Args:
            table: DeltaTable instance
            current_version: Current version number to analyze up to
            retention_hours: Retention period in hours (default: 168 = 7 days)
            storage_options: Optional cloud storage credentials and configuration

        Returns:
            Dictionary containing:
            - active_files: Dict with count and total_size_bytes of active files
            - tombstone_files: Dict with count and total_size_bytes of tombstoned files
            - waste_percentage: Percentage of storage that is tombstoned (0-100)
            - reclaimable_bytes: Bytes that can be safely vacuumed (beyond retention)
            - retention_period_hours: Configured retention period
            - total_storage_bytes: Total storage (active + tombstone)

        Examples:
            >>> dt = DeltaTable("./my_table")
            >>> analysis = DeltaForensics.analyze_storage_waste(dt, dt.version())
            >>> print(f"Waste: {analysis['waste_percentage']}%")
            >>> print(f"Reclaimable: {analysis['reclaimable_bytes'] / (1024**3):.2f} GB")
        """
        # Get table URI for accessing transaction log
        table_uri = table.table_uri

        # Create filesystem abstraction
        fs = DeltaLogFileSystem(table_uri, storage_options)

        # Track active and tombstoned files
        active_files: dict[str, int] = {}  # path -> size
        tombstoned_files: dict[str, tuple[int, int]] = {}  # path -> (size, deletion_timestamp)

        # Parse all versions up to current_version
        for version in range(current_version + 1):
            # Read version file using filesystem abstraction
            parsed = fs.read_version_file(version)
            if parsed is None:
                continue

            try:
                # Process add actions - add to active files
                for add_action in parsed["add_actions"]:
                    active_files[add_action.path] = add_action.size
                    # If file was previously tombstoned, remove from tombstones
                    if add_action.path in tombstoned_files:
                        del tombstoned_files[add_action.path]

                # Process remove actions - move to tombstoned files
                for remove_action in parsed["remove_actions"]:
                    if remove_action.path in active_files:
                        # Move from active to tombstoned
                        size = active_files.pop(remove_action.path)
                        tombstoned_files[remove_action.path] = (
                            size,
                            remove_action.deletion_timestamp,
                        )
                    elif remove_action.size is not None:
                        # File not in active (maybe from earlier version we didn't parse)
                        tombstoned_files[remove_action.path] = (
                            remove_action.size,
                            remove_action.deletion_timestamp,
                        )

            except Exception as e:  # nosec B112
                # Skip versions that can't be parsed - this is intentional for robustness
                logger.debug(f"Failed to parse version {version} for storage waste analysis: {e}")
                continue

        # Calculate statistics
        active_count = len(active_files)
        active_size = sum(active_files.values())

        tombstone_count = len(tombstoned_files)
        tombstone_size = sum(size for size, _ in tombstoned_files.values())

        total_storage = active_size + tombstone_size
        waste_percentage = (tombstone_size / total_storage * 100.0) if total_storage > 0 else 0.0

        # Calculate reclaimable storage (files beyond retention period)
        # Get current timestamp from the current version
        current_timestamp = 0
        parsed = fs.read_version_file(current_version)
        if parsed and parsed["commit_info"]:
            current_timestamp = parsed["commit_info"].timestamp

        # If we couldn't get timestamp from version file, use current time as fallback
        if current_timestamp == 0:
            current_timestamp = int(time.time() * 1000)  # Convert to milliseconds

        # Calculate retention threshold
        retention_ms = retention_hours * 60 * 60 * 1000
        retention_threshold = current_timestamp - retention_ms

        # Sum up files that are beyond retention
        reclaimable_bytes = sum(
            size
            for size, deletion_ts in tombstoned_files.values()
            if deletion_ts < retention_threshold and deletion_ts > 0
        )

        return {
            "active_files": {
                "count": active_count,
                "total_size_bytes": active_size,
            },
            "tombstone_files": {
                "count": tombstone_count,
                "total_size_bytes": tombstone_size,
            },
            "waste_percentage": round(waste_percentage, 2),
            "reclaimable_bytes": reclaimable_bytes,
            "retention_period_hours": retention_hours,
            "total_storage_bytes": total_storage,
        }

    @staticmethod
    def analyze_dml_operation(
        commit_info: dict[str, Any], operation_metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze DML operation impact (MERGE, UPDATE, DELETE).

        Calculates rewrite amplification and efficiency metrics for data manipulation
        operations to identify inefficient query patterns.

        Args:
            commit_info: Commit info dictionary from transaction log
            operation_metrics: Normalized operation metrics

        Returns:
            Dictionary containing:
            - operation_type: Type of DML operation (MERGE, UPDATE, DELETE)
            - rewrite_amplification: Ratio of data rewritten to data changed (>= 1.0)
            - rows_affected: Total rows changed by the operation
            - files_rewritten: Number of files rewritten
            - efficiency_score: 0-100 rating (100 = most efficient)
            - is_inefficient: Boolean flag if amplification > 10x
            - merge_metrics: MERGE-specific metrics (if applicable)
                - rows_matched: Rows matched by merge predicate
                - rows_inserted: Rows inserted
                - merge_predicate: Merge predicate expression (if available)

        Examples:
            >>> commit_info = {...}
            >>> metrics = DeltaLogParser.extract_operation_metrics(commit_info)
            >>> analysis = DeltaForensics.analyze_dml_operation(commit_info, metrics)
            >>> if analysis['is_inefficient']:
            ...     print(f"High amplification: {analysis['rewrite_amplification']}x")
        """
        operation_type = commit_info.get("operation", "UNKNOWN")

        # Extract relevant metrics
        bytes_added = int(operation_metrics.get("num_bytes_added", 0))
        bytes_removed = int(operation_metrics.get("num_bytes_removed", 0))
        output_bytes = int(operation_metrics.get("num_output_bytes", 0))

        files_added = int(operation_metrics.get("num_added_files", 0))
        files_removed = int(operation_metrics.get("num_removed_files", 0))

        # Calculate rows affected based on operation type
        rows_affected = 0
        if operation_type == "MERGE":
            rows_affected = (
                int(operation_metrics.get("num_target_rows_inserted", 0))
                + int(operation_metrics.get("num_target_rows_updated", 0))
                + int(operation_metrics.get("num_target_rows_deleted", 0))
            )
        elif operation_type == "UPDATE":
            rows_affected = int(operation_metrics.get("num_target_rows_updated", 0))
        elif operation_type == "DELETE":
            rows_affected = int(operation_metrics.get("num_deleted_rows", 0))
        else:
            rows_affected = int(operation_metrics.get("num_output_rows", 0))

        # Calculate rewrite amplification
        # Amplification = (bytes written) / (net bytes changed)
        # For DML operations, we rewrite entire files even if only a few rows change
        bytes_rewritten = bytes_added
        bytes_changed = abs(bytes_added - bytes_removed)

        # Avoid division by zero
        if bytes_changed > 0:
            rewrite_amplification = bytes_rewritten / bytes_changed
        elif bytes_rewritten > 0:
            # All bytes were added (no removal), amplification is 1.0
            rewrite_amplification = 1.0
        else:
            # No bytes changed
            rewrite_amplification = 0.0

        # Calculate efficiency score (0-100)
        # Perfect efficiency (1.0x amplification) = 100
        # 10x amplification = 10
        # 100x amplification = 1
        if rewrite_amplification > 0:
            efficiency_score = max(0, min(100, 100 / rewrite_amplification))
        else:
            efficiency_score = 100.0

        # Flag inefficient operations (> 10x amplification)
        is_inefficient = rewrite_amplification > 10.0

        # Build result
        result: dict[str, Any] = {
            "operation_type": operation_type,
            "rewrite_amplification": round(rewrite_amplification, 2),
            "rows_affected": rows_affected,
            "files_rewritten": max(files_added, files_removed),
            "efficiency_score": round(efficiency_score, 2),
            "is_inefficient": is_inefficient,
        }

        # Add MERGE-specific metrics
        if operation_type == "MERGE":
            merge_metrics = {
                "rows_matched": (
                    int(operation_metrics.get("num_target_rows_matched_updated", 0))
                    + int(operation_metrics.get("num_target_rows_matched_deleted", 0))
                ),
                "rows_inserted": int(operation_metrics.get("num_target_rows_inserted", 0)),
                "rows_updated": int(operation_metrics.get("num_target_rows_updated", 0)),
                "rows_deleted": int(operation_metrics.get("num_target_rows_deleted", 0)),
            }

            # Extract merge predicate from operation parameters if available
            operation_params = commit_info.get("operationParameters", {})
            if "predicate" in operation_params:
                merge_metrics["merge_predicate"] = operation_params["predicate"]

            result["merge_metrics"] = merge_metrics

        return result

    @staticmethod
    def analyze_zorder_effectiveness(
        table: DeltaTable,
        zorder_columns: list[str] | None = None,
        storage_options: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Analyze Z-order clustering effectiveness.

        Evaluates how well Z-order clustering is working by analyzing min/max
        statistics overlap and estimating data skipping effectiveness.

        Args:
            table: DeltaTable instance
            zorder_columns: List of Z-ordered columns (if None, will auto-detect)
            storage_options: Optional cloud storage credentials and configuration

        Returns:
            Dictionary containing:
            - zorder_columns: List of columns used for Z-ordering
            - last_optimize_version: Version of last OPTIMIZE operation (or None)
            - data_skipping_effectiveness: Dict mapping column -> percentage (0-100)
            - overall_effectiveness: Average effectiveness across all columns (0-100)
            - degradation_since_optimize: Estimated degradation percentage
            - recommendation: "good", "degraded", or "needs_reoptimization"
            - versions_since_optimize: Number of versions since last OPTIMIZE

        Examples:
            >>> dt = DeltaTable("./my_table")
            >>> analysis = DeltaForensics.analyze_zorder_effectiveness(dt, ["user_id", "date"])
            >>> print(f"Effectiveness: {analysis['overall_effectiveness']}%")
            >>> if analysis['recommendation'] == 'needs_reoptimization':
            ...     print("Consider running OPTIMIZE ZORDER")
        """
        # Get table URI for accessing transaction log
        table_uri = table.table_uri

        # Create filesystem abstraction
        fs = DeltaLogFileSystem(table_uri, storage_options)
        current_version = table.version()

        # Auto-detect Z-order columns if not provided
        if zorder_columns is None:
            zorder_columns = []
            # Look for OPTIMIZE operations with zOrderBy parameter
            for version in range(current_version, -1, -1):
                parsed = fs.read_version_file(version)
                if parsed is None:
                    continue

                try:
                    commit_info = parsed["commit_info"]

                    if commit_info and commit_info.operation == "OPTIMIZE":
                        params = commit_info.operation_parameters
                        if "zOrderBy" in params:
                            # Parse zOrderBy parameter (usually a JSON array string)
                            import json

                            zorder_str = params["zOrderBy"]
                            if isinstance(zorder_str, str):
                                try:
                                    zorder_columns = json.loads(zorder_str)
                                except json.JSONDecodeError:
                                    # Might be a simple string
                                    zorder_columns = [zorder_str]
                            elif isinstance(zorder_str, list):
                                zorder_columns = zorder_str
                            break
                except Exception as e:  # nosec B112
                    # Skip versions with parsing errors - continue searching
                    logger.debug(f"Failed to parse version {version} for Z-order columns: {e}")
                    continue

        # Find last OPTIMIZE operation
        last_optimize_version: int | None = None
        for version in range(current_version, -1, -1):
            parsed = fs.read_version_file(version)
            if parsed is None:
                continue

            try:
                commit_info = parsed["commit_info"]

                if commit_info and commit_info.operation == "OPTIMIZE":
                    last_optimize_version = version
                    break
            except Exception as e:  # nosec B112
                # Skip versions with parsing errors - continue searching
                logger.debug(f"Failed to parse version {version} for OPTIMIZE operation: {e}")
                continue

        versions_since_optimize = (
            current_version - last_optimize_version
            if last_optimize_version is not None
            else current_version + 1
        )

        # Calculate data skipping effectiveness
        # This is a simplified heuristic based on file statistics
        data_skipping_effectiveness: dict[str, float] = {}

        if zorder_columns:
            # Accumulate all active files from version 0 to current version
            # This gives us the complete state of the table at the current version
            active_files: dict[str, AddAction] = {}  # path -> AddAction

            for v in range(current_version + 1):
                parsed = fs.read_version_file(v)
                if parsed is None:
                    continue

                try:
                    # Add new files
                    for add_action in parsed["add_actions"]:
                        active_files[add_action.path] = add_action

                    # Remove deleted files
                    for remove_action in parsed["remove_actions"]:
                        if remove_action.path in active_files:
                            del active_files[remove_action.path]

                except Exception as e:  # nosec B112
                    logger.debug(f"Failed to parse version {v} for active files: {e}")
                    continue

            # Use all active files for analysis
            add_actions = list(active_files.values())

            if add_actions:
                try:
                    # For each Z-ordered column, calculate overlap
                    for col in zorder_columns:
                        # Extract min/max values from file stats
                        min_values = []
                        max_values = []

                        for action in add_actions:
                            if (
                                action.stats
                                and "minValues" in action.stats
                                and "maxValues" in action.stats
                            ):
                                min_vals = action.stats["minValues"]
                                max_vals = action.stats["maxValues"]

                                if col in min_vals and col in max_vals:
                                    min_values.append(min_vals[col])
                                    max_values.append(max_vals[col])

                        # Calculate effectiveness based on overlap
                        # High effectiveness = low overlap between file ranges
                        # This is a simplified heuristic
                        if len(min_values) >= 2:
                            # Sort files by min value
                            file_ranges = sorted(zip(min_values, max_values, strict=True))

                            # Calculate average overlap
                            total_overlap = 0
                            for i in range(len(file_ranges) - 1):
                                _, max_i = file_ranges[i]
                                min_next, _ = file_ranges[i + 1]

                                # Check if ranges overlap
                                if max_i > min_next:
                                    total_overlap += 1

                            # Effectiveness = (1 - overlap_ratio) * 100
                            overlap_ratio = total_overlap / (len(file_ranges) - 1)
                            effectiveness = (1 - overlap_ratio) * 100
                            data_skipping_effectiveness[col] = round(effectiveness, 2)
                        else:
                            # Not enough files to calculate effectiveness
                            data_skipping_effectiveness[col] = 100.0

                except Exception:
                    # If we can't parse stats, assume moderate effectiveness
                    for col in zorder_columns:
                        data_skipping_effectiveness[col] = 70.0
            else:
                # No active files found, assume moderate effectiveness
                for col in zorder_columns:
                    data_skipping_effectiveness[col] = 70.0

        # Calculate overall effectiveness
        if data_skipping_effectiveness:
            overall_effectiveness = round(
                sum(data_skipping_effectiveness.values()) / len(data_skipping_effectiveness), 2
            )
        else:
            overall_effectiveness = 0.0

        # Estimate degradation since last optimize
        # Heuristic: effectiveness degrades by ~5% per version after optimize
        degradation_since_optimize = min(100.0, versions_since_optimize * 5.0)

        # Determine recommendation
        if overall_effectiveness >= 80:
            recommendation = "good"
        elif overall_effectiveness >= 60:
            recommendation = "degraded"
        else:
            recommendation = "needs_reoptimization"

        return {
            "zorder_columns": zorder_columns,
            "last_optimize_version": last_optimize_version,
            "data_skipping_effectiveness": data_skipping_effectiveness,
            "overall_effectiveness": overall_effectiveness,
            "degradation_since_optimize": round(degradation_since_optimize, 2),
            "recommendation": recommendation,
            "versions_since_optimize": versions_since_optimize,
        }

    @staticmethod
    def analyze_checkpoint_health(
        table: DeltaTable, storage_options: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Analyze checkpoint health and efficiency.

        Evaluates the health of Delta table checkpoints by analyzing checkpoint
        age, log tail length, and identifying missing or corrupted checkpoints.

        Args:
            table: DeltaTable instance
            storage_options: Optional cloud storage credentials and configuration

        Returns:
            Dictionary containing:
            - last_checkpoint_version: Version number of last checkpoint (or None)
            - log_tail_length: Number of JSON files since last checkpoint
            - checkpoint_age_hours: Hours since last checkpoint was created
            - checkpoint_file_size_bytes: Size of checkpoint file (or None)
            - health_status: "healthy", "degraded", or "critical"
            - issues: List of identified issues
            - recommendation: Suggested action (or None)

        Examples:
            >>> dt = DeltaTable("./my_table")
            >>> health = DeltaForensics.analyze_checkpoint_health(dt)
            >>> print(f"Status: {health['health_status']}")
            >>> if health['log_tail_length'] > 10:
            ...     print("Consider creating a new checkpoint")
        """
        # Get table URI for accessing transaction log
        table_uri = table.table_uri

        # Create filesystem abstraction
        fs = DeltaLogFileSystem(table_uri, storage_options)
        current_version = table.version()

        # Find checkpoint files
        checkpoint_files = fs.list_checkpoint_files()

        last_checkpoint_version: int | None = None
        checkpoint_file_size_bytes: int | None = None
        checkpoint_timestamp: int | None = None

        if checkpoint_files:
            # Extract version numbers from checkpoint filenames
            checkpoint_versions: dict[
                int, list[str]
            ] = {}  # version -> list of checkpoint file paths
            for cp_file in checkpoint_files:
                try:
                    # Extract version from filename
                    # Single file: "00000000000000000010.checkpoint.parquet"
                    # Multi-part: "00000000000000000010.checkpoint.0000000001.0000000010.parquet"
                    filename = Path(cp_file).name

                    filename_parts = filename.replace(".parquet", "").split(".")
                    version_str = filename_parts[0]
                    version = int(version_str)

                    if version not in checkpoint_versions:
                        checkpoint_versions[version] = []
                    checkpoint_versions[version].append(cp_file)
                except (ValueError, IndexError):
                    continue

            if checkpoint_versions:
                # Get the most recent checkpoint version
                last_checkpoint_version = max(checkpoint_versions.keys())

                # Calculate total size of all checkpoint files for this version
                checkpoint_files_for_version = checkpoint_versions[last_checkpoint_version]

                # Get total size of checkpoint files
                checkpoint_file_size_bytes = 0
                for cp_file in checkpoint_files_for_version:
                    size = fs.get_checkpoint_file_size(cp_file)
                    if size is not None:
                        checkpoint_file_size_bytes += size

                # Try to get checkpoint timestamp from the corresponding version file
                parsed = fs.read_version_file(last_checkpoint_version)
                if parsed and parsed["commit_info"]:
                    checkpoint_timestamp = parsed["commit_info"].timestamp

        # Calculate log tail length (JSON files since last checkpoint)
        if last_checkpoint_version is not None:
            log_tail_length = current_version - last_checkpoint_version
        else:
            log_tail_length = current_version + 1  # All versions are in the tail

        # Calculate checkpoint age
        checkpoint_age_hours: float | None = None
        if checkpoint_timestamp is not None:
            # Get current timestamp from current version
            parsed = fs.read_version_file(current_version)
            if parsed and parsed["commit_info"]:
                current_timestamp = parsed["commit_info"].timestamp
                age_ms = current_timestamp - checkpoint_timestamp
                checkpoint_age_hours = age_ms / (1000 * 60 * 60)

        # Determine health status and issues
        issues: list[str] = []

        if last_checkpoint_version is None:
            health_status = "critical"
            issues.append("No checkpoint found")
        elif log_tail_length > 20:
            health_status = "critical"
            issues.append(f"Log tail too long ({log_tail_length} files)")
        elif log_tail_length > 10:
            health_status = "degraded"
            issues.append(f"Log tail growing ({log_tail_length} files)")
        else:
            health_status = "healthy"

        # Check if checkpoint file is accessible
        if last_checkpoint_version is not None and checkpoint_file_size_bytes is not None:
            if checkpoint_file_size_bytes == 0:
                health_status = "critical"
                issues.append("Checkpoint file is empty or corrupted")

        # Generate recommendation
        recommendation: str | None = None
        if health_status == "critical":
            if last_checkpoint_version is None:
                recommendation = "Create initial checkpoint"
            elif log_tail_length > 20:
                recommendation = "Create new checkpoint immediately"
            else:
                recommendation = "Repair or recreate checkpoint"
        elif health_status == "degraded":
            recommendation = "Consider creating a new checkpoint"

        return {
            "last_checkpoint_version": last_checkpoint_version,
            "log_tail_length": log_tail_length,
            "checkpoint_age_hours": round(checkpoint_age_hours, 2)
            if checkpoint_age_hours is not None
            else None,
            "checkpoint_file_size_bytes": checkpoint_file_size_bytes,
            "health_status": health_status,
            "issues": issues,
            "recommendation": recommendation,
        }

    @staticmethod
    def generate_recommendations(
        table: DeltaTable, snapshot: SnapshotInfo, storage_options: dict[str, str] | None = None
    ) -> list[dict[str, Any]]:
        """Generate actionable optimization recommendations.

        Analyzes the table and current snapshot to generate prioritized
        recommendations for OPTIMIZE, VACUUM, ZORDER, and CHECKPOINT operations.

        Args:
            table: DeltaTable instance
            snapshot: Current SnapshotInfo
            storage_options: Optional cloud storage credentials and configuration

        Returns:
            List of recommendation dictionaries, each containing:
            - type: "OPTIMIZE", "VACUUM", "ZORDER", or "CHECKPOINT"
            - priority: "high", "medium", or "low"
            - reason: Explanation of why this is recommended
            - estimated_impact: Quantified benefit description
            - command: Suggested command to run
            - details: Additional context (optional)

        Examples:
            >>> dt = DeltaTable("./my_table")
            >>> snapshot = adapter.load_snapshot(table, None)
            >>> recommendations = DeltaForensics.generate_recommendations(dt, snapshot)
            >>> for rec in recommendations:
            ...     print(f"{rec['priority'].upper()}: {rec['type']} - {rec['reason']}")
        """
        recommendations: list[dict[str, Any]] = []

        # Analyze file sizes
        file_analysis = DeltaForensics.analyze_file_sizes(snapshot)

        # Recommendation 1: OPTIMIZE for small files
        if file_analysis["small_file_percentage"] > 50:
            priority = "high"
            estimated_reduction = file_analysis["optimization_opportunity"]
            recommendations.append(
                {
                    "type": "OPTIMIZE",
                    "priority": priority,
                    "reason": f"{file_analysis['small_file_percentage']}% of files are smaller than 10MB",
                    "estimated_impact": f"Reduce file count by ~{estimated_reduction} files ({estimated_reduction / file_analysis['total_file_count'] * 100:.0f}%)",
                    "command": "OPTIMIZE table_name",
                    "details": {
                        "small_file_count": file_analysis["small_file_count"],
                        "total_file_count": file_analysis["total_file_count"],
                        "estimated_reduction": estimated_reduction,
                    },
                }
            )
        elif file_analysis["small_file_percentage"] > 30:
            priority = "medium"
            estimated_reduction = file_analysis["optimization_opportunity"]
            recommendations.append(
                {
                    "type": "OPTIMIZE",
                    "priority": priority,
                    "reason": f"{file_analysis['small_file_percentage']}% of files are smaller than 10MB",
                    "estimated_impact": f"Reduce file count by ~{estimated_reduction} files",
                    "command": "OPTIMIZE table_name",
                    "details": {
                        "small_file_count": file_analysis["small_file_count"],
                        "total_file_count": file_analysis["total_file_count"],
                    },
                }
            )

        # Analyze storage waste
        try:
            storage_analysis = DeltaForensics.analyze_storage_waste(
                table, table.version(), storage_options=storage_options
            )

            # Recommendation 2: VACUUM for storage waste
            if storage_analysis["waste_percentage"] > 30:
                priority = "high"
                reclaimable_gb = storage_analysis["reclaimable_bytes"] / (1024**3)
                recommendations.append(
                    {
                        "type": "VACUUM",
                        "priority": priority,
                        "reason": f"Storage waste is {storage_analysis['waste_percentage']}% of total table size",
                        "estimated_impact": f"Reclaim ~{reclaimable_gb:.2f} GB of storage",
                        "command": f"VACUUM table_name RETAIN {storage_analysis['retention_period_hours']} HOURS",
                        "details": {
                            "waste_percentage": storage_analysis["waste_percentage"],
                            "tombstone_count": storage_analysis["tombstone_files"]["count"],
                            "reclaimable_bytes": storage_analysis["reclaimable_bytes"],
                        },
                    }
                )
            elif storage_analysis["waste_percentage"] > 15:
                priority = "medium"
                reclaimable_gb = storage_analysis["reclaimable_bytes"] / (1024**3)
                recommendations.append(
                    {
                        "type": "VACUUM",
                        "priority": priority,
                        "reason": f"Storage waste is {storage_analysis['waste_percentage']}%",
                        "estimated_impact": f"Reclaim ~{reclaimable_gb:.2f} GB",
                        "command": f"VACUUM table_name RETAIN {storage_analysis['retention_period_hours']} HOURS",
                    }
                )
        except Exception as e:  # nosec B110
            # Storage analysis might fail for some tables - gracefully skip
            logger.debug(f"Storage waste analysis failed: {e}")
            pass

        # Analyze Z-order effectiveness
        try:
            zorder_analysis = DeltaForensics.analyze_zorder_effectiveness(
                table, storage_options=storage_options
            )

            # Recommendation 3: ZORDER for degraded effectiveness
            if (
                zorder_analysis["zorder_columns"]
                and zorder_analysis["recommendation"] == "needs_reoptimization"
            ):
                priority = "high"
                columns_str = ", ".join(zorder_analysis["zorder_columns"])
                recommendations.append(
                    {
                        "type": "ZORDER",
                        "priority": priority,
                        "reason": f"Data skipping effectiveness is {zorder_analysis['overall_effectiveness']}% (below 60% threshold)",
                        "estimated_impact": f"Improve query performance by re-clustering on {columns_str}",
                        "command": f"OPTIMIZE table_name ZORDER BY ({columns_str})",
                        "details": {
                            "zorder_columns": zorder_analysis["zorder_columns"],
                            "overall_effectiveness": zorder_analysis["overall_effectiveness"],
                            "versions_since_optimize": zorder_analysis["versions_since_optimize"],
                        },
                    }
                )
            elif (
                zorder_analysis["zorder_columns"]
                and zorder_analysis["recommendation"] == "degraded"
            ):
                priority = "low"
                columns_str = ", ".join(zorder_analysis["zorder_columns"])
                recommendations.append(
                    {
                        "type": "ZORDER",
                        "priority": priority,
                        "reason": f"Data skipping effectiveness is {zorder_analysis['overall_effectiveness']}% (degraded)",
                        "estimated_impact": "Maintain query performance",
                        "command": f"OPTIMIZE table_name ZORDER BY ({columns_str})",
                    }
                )
        except Exception as e:  # nosec B110
            # Z-order analysis might fail for some tables - gracefully skip
            logger.debug(f"Z-order effectiveness analysis failed: {e}")
            pass

        # Analyze checkpoint health
        try:
            checkpoint_health = DeltaForensics.analyze_checkpoint_health(
                table, storage_options=storage_options
            )

            # Recommendation 4: CHECKPOINT for long log tail
            if checkpoint_health["health_status"] == "critical":
                priority = "high"
                recommendations.append(
                    {
                        "type": "CHECKPOINT",
                        "priority": priority,
                        "reason": checkpoint_health["issues"][0]
                        if checkpoint_health["issues"]
                        else "Checkpoint health is critical",
                        "estimated_impact": "Improve metadata read performance",
                        "command": "CREATE CHECKPOINT (implementation-specific)",
                        "details": {
                            "log_tail_length": checkpoint_health["log_tail_length"],
                            "health_status": checkpoint_health["health_status"],
                        },
                    }
                )
            elif checkpoint_health["health_status"] == "degraded":
                priority = "medium"
                recommendations.append(
                    {
                        "type": "CHECKPOINT",
                        "priority": priority,
                        "reason": f"Log tail has {checkpoint_health['log_tail_length']} files",
                        "estimated_impact": "Maintain metadata read performance",
                        "command": "CREATE CHECKPOINT (implementation-specific)",
                    }
                )
        except Exception as e:  # nosec B110
            # Checkpoint analysis might fail for some tables - gracefully skip
            logger.debug(f"Checkpoint health analysis failed: {e}")
            pass

        # Sort recommendations by priority (high -> medium -> low)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda x: priority_order[x["priority"]])

        return recommendations

    @staticmethod
    def analyze_partition_distribution(
        snapshot: SnapshotInfo, partition_columns: list[str] | None = None
    ) -> dict[str, Any]:
        """Analyze partition distribution and detect skew.

        Evaluates how data is distributed across partitions and identifies
        hot partitions that may cause performance issues.

        Args:
            snapshot: SnapshotInfo containing data files
            partition_columns: List of partition column names (auto-detected if None)

        Returns:
            Dictionary containing:
            - partition_columns: List of partition column names
            - partition_count: Total number of partitions
            - files_per_partition: Dict mapping partition key -> file count
            - rows_per_partition: Dict mapping partition key -> row count (if available)
            - bytes_per_partition: Dict mapping partition key -> total bytes
            - statistics: Dict with min, max, avg, median files per partition
            - skewed_partitions: List of partitions with > 2x average
            - hot_partitions: List of partitions with > 3x average
            - skew_ratio: Ratio of max to average files per partition
            - recommendation: Suggested action (or None)

        Examples:
            >>> snapshot = SnapshotInfo(...)
            >>> analysis = DeltaForensics.analyze_partition_distribution(snapshot)
            >>> if analysis['hot_partitions']:
            ...     print(f"Hot partitions detected: {analysis['hot_partitions']}")
        """
        # Auto-detect partition columns from first file
        if partition_columns is None:
            partition_columns = []
            if snapshot.data_files:
                first_file = snapshot.data_files[0]
                if first_file.partition:
                    partition_columns = list(first_file.partition.keys())

        # If no partitions, return empty analysis
        if not partition_columns or not snapshot.data_files:
            return {
                "partition_columns": partition_columns,
                "partition_count": 0,
                "files_per_partition": {},
                "rows_per_partition": {},
                "bytes_per_partition": {},
                "statistics": {},
                "skewed_partitions": [],
                "hot_partitions": [],
                "skew_ratio": 0.0,
                "recommendation": None,
            }

        # Aggregate data by partition
        files_per_partition: dict[str, int] = {}
        rows_per_partition: dict[str, int] = {}
        bytes_per_partition: dict[str, int] = {}

        for file in snapshot.data_files:
            if not file.partition:
                continue

            # Create partition key from partition values
            partition_key = ",".join(
                f"{col}={file.partition.get(col, 'null')}" for col in partition_columns
            )

            # Count files
            files_per_partition[partition_key] = files_per_partition.get(partition_key, 0) + 1

            # Count rows (if available)
            if file.record_count is not None:
                rows_per_partition[partition_key] = (
                    rows_per_partition.get(partition_key, 0) + file.record_count
                )

            # Sum bytes
            bytes_per_partition[partition_key] = (
                bytes_per_partition.get(partition_key, 0) + file.file_size_bytes
            )

        partition_count = len(files_per_partition)

        # Calculate statistics
        file_counts = list(files_per_partition.values())
        if file_counts:
            min_files = min(file_counts)
            max_files = max(file_counts)
            avg_files = sum(file_counts) / len(file_counts)
            median_files = statistics.median(file_counts)

            statistics_dict = {
                "min_files_per_partition": min_files,
                "max_files_per_partition": max_files,
                "avg_files_per_partition": round(avg_files, 2),
                "median_files_per_partition": median_files,
            }

            # Calculate skew ratio
            skew_ratio = max_files / avg_files if avg_files > 0 else 0.0
        else:
            statistics_dict = {}
            skew_ratio = 0.0

        # Identify skewed and hot partitions
        skewed_partitions: list[str] = []
        hot_partitions: list[str] = []

        if file_counts:
            avg_files = sum(file_counts) / len(file_counts)

            for partition_key, file_count in files_per_partition.items():
                if file_count > avg_files * 3:
                    hot_partitions.append(partition_key)
                elif file_count > avg_files * 2:
                    skewed_partitions.append(partition_key)

        # Generate recommendation
        recommendation: str | None = None
        if hot_partitions:
            recommendation = f"Consider sub-partitioning or repartitioning {len(hot_partitions)} hot partition(s)"
        elif skewed_partitions:
            recommendation = (
                f"Monitor {len(skewed_partitions)} skewed partition(s) for potential issues"
            )

        return {
            "partition_columns": partition_columns,
            "partition_count": partition_count,
            "files_per_partition": files_per_partition,
            "rows_per_partition": rows_per_partition,
            "bytes_per_partition": bytes_per_partition,
            "statistics": statistics_dict,
            "skewed_partitions": skewed_partitions,
            "hot_partitions": hot_partitions,
            "skew_ratio": round(skew_ratio, 2),
            "recommendation": recommendation,
        }

    @staticmethod
    def track_rewrite_amplification(
        table: DeltaTable, max_versions: int = 100, storage_options: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Track rewrite amplification across DML operations over time.

        Analyzes historical DML operations to identify trends in rewrite
        amplification and highlight the most inefficient operations.

        Args:
            table: DeltaTable instance
            max_versions: Maximum number of recent versions to analyze
            storage_options: Optional cloud storage credentials and configuration

        Returns:
            Dictionary containing:
            - dml_operations: List of DML operation analyses with amplification
            - trend: "increasing", "stable", or "decreasing"
            - highest_amplification: Dict with details of worst operation
            - average_amplification: Average across all DML operations
            - operations_above_threshold: Count of operations with > 10x amplification
            - extreme_operations: List of operations with > 20x amplification
            - recommendation: Suggested action (or None)

        Examples:
            >>> dt = DeltaTable("./my_table")
            >>> tracking = DeltaForensics.track_rewrite_amplification(dt)
            >>> if tracking['trend'] == 'increasing':
            ...     print("Amplification is getting worse over time")
        """
        # Get table URI for accessing transaction log
        table_uri = table.table_uri

        # Create filesystem abstraction
        fs = DeltaLogFileSystem(table_uri, storage_options)
        current_version = table.version()

        # Determine version range to analyze
        start_version = max(0, current_version - max_versions + 1)

        # Collect DML operations
        dml_operations: list[dict[str, Any]] = []

        for version in range(start_version, current_version + 1):
            parsed = fs.read_version_file(version)
            if parsed is None:
                continue

            try:
                commit_info = parsed["commit_info"]

                if not commit_info:
                    continue

                # Only analyze DML operations
                if commit_info.operation not in ["MERGE", "UPDATE", "DELETE"]:
                    continue

                # Extract and normalize metrics
                operation_metrics = DeltaLogParser.extract_operation_metrics(
                    {"operationMetrics": commit_info.operation_metrics}
                )

                # Analyze the operation
                analysis = DeltaForensics.analyze_dml_operation(
                    {
                        "operation": commit_info.operation,
                        "operationParameters": commit_info.operation_parameters,
                        "operationMetrics": commit_info.operation_metrics,
                    },
                    operation_metrics,
                )

                # Add version and timestamp
                analysis["version"] = version
                analysis["timestamp_ms"] = commit_info.timestamp

                dml_operations.append(analysis)

            except Exception as e:  # nosec B112
                # Skip versions with parsing errors - continue searching
                logger.debug(f"Failed to analyze DML operation at version {version}: {e}")
                continue

        # Calculate statistics
        if not dml_operations:
            return {
                "dml_operations": [],
                "trend": "stable",
                "highest_amplification": None,
                "average_amplification": 0.0,
                "operations_above_threshold": 0,
                "extreme_operations": [],
                "recommendation": None,
            }

        # Sort by amplification (highest first)
        sorted_operations = sorted(
            dml_operations, key=lambda x: x["rewrite_amplification"], reverse=True
        )

        highest_amplification = sorted_operations[0]

        # Calculate average amplification
        amplifications = [op["rewrite_amplification"] for op in dml_operations]
        average_amplification = sum(amplifications) / len(amplifications)

        # Count operations above threshold
        operations_above_threshold = sum(1 for amp in amplifications if amp > 10.0)

        # Identify extreme operations (> 20x)
        extreme_operations = [op for op in dml_operations if op["rewrite_amplification"] > 20.0]

        # Analyze trend (simple linear regression on recent operations)
        trend = "stable"
        if len(dml_operations) >= 3:
            # Compare first half to second half
            mid_point = len(dml_operations) // 2
            first_half_avg = sum(amplifications[:mid_point]) / mid_point
            second_half_avg = sum(amplifications[mid_point:]) / (len(amplifications) - mid_point)

            # If second half is 20% higher, trend is increasing
            if second_half_avg > first_half_avg * 1.2:
                trend = "increasing"
            elif second_half_avg < first_half_avg * 0.8:
                trend = "decreasing"

        # Generate recommendation
        recommendation: str | None = None
        if trend == "increasing":
            recommendation = (
                "Rewrite amplification is increasing - review partitioning and clustering strategy"
            )
        elif extreme_operations:
            recommendation = f"Found {len(extreme_operations)} operation(s) with extreme amplification (>20x) - investigate and optimize"
        elif operations_above_threshold > len(dml_operations) * 0.5:
            recommendation = (
                "More than 50% of DML operations have high amplification - consider table redesign"
            )

        return {
            "dml_operations": dml_operations,
            "trend": trend,
            "highest_amplification": highest_amplification,
            "average_amplification": round(average_amplification, 2),
            "operations_above_threshold": operations_above_threshold,
            "extreme_operations": extreme_operations,
            "recommendation": recommendation,
        }
