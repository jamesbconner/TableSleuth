"""Delta Lake transaction log parser.

This module provides utilities for parsing Delta Lake's JSON transaction log files
and extracting commit information, add actions, and remove actions.

Supports both local filesystem and cloud storage (S3, Azure, GCS) via PyArrow filesystem.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from pyarrow import fs as pafs
except ImportError:
    pafs = None

logger = logging.getLogger(__name__)


@dataclass
class CommitInfo:
    """Parsed commit information from transaction log.

    Attributes:
        timestamp: Milliseconds since epoch
        operation: Operation type (WRITE, MERGE, UPDATE, DELETE, OPTIMIZE, VACUUM)
        operation_parameters: Operation-specific parameters
        operation_metrics: Metrics like rows, bytes, files
        user_metadata: Custom metadata (optional)
        engine_info: Tool that performed the operation (optional)
    """

    timestamp: int
    operation: str
    operation_parameters: dict[str, Any]
    operation_metrics: dict[str, Any]
    user_metadata: str | None = None
    engine_info: str | None = None


@dataclass
class AddAction:
    """Parsed add action from transaction log.

    Attributes:
        path: Relative path to Parquet file
        size: File size in bytes
        modification_time: File modification timestamp
        data_change: Whether this is a data change (vs metadata)
        stats: File statistics (optional)
        partition_values: Partition column values
    """

    path: str
    size: int
    modification_time: int
    data_change: bool
    stats: dict[str, Any] | None
    partition_values: dict[str, str]


@dataclass
class RemoveAction:
    """Parsed remove action from transaction log.

    Attributes:
        path: Path to removed file
        deletion_timestamp: When file was removed
        data_change: Whether this is a data change
        size: File size (if available)
    """

    path: str
    deletion_timestamp: int
    data_change: bool
    size: int | None = None


class DeltaLogParser:
    """Parser for Delta Lake transaction log JSON files."""

    @staticmethod
    def parse_version_file(
        file_path: str, filesystem: pafs.FileSystem | None = None
    ) -> dict[str, Any]:
        """Parse a single version JSON file from local or cloud storage.

        Args:
            file_path: Path to the version JSON file (local path or cloud URI path component)
            filesystem: PyArrow filesystem for cloud storage (None for local files)

        Returns:
            Dictionary with:
            - commit_info: CommitInfo object (or None if not present)
            - add_actions: list of AddAction objects
            - remove_actions: list of RemoveAction objects

        Raises:
            FileNotFoundError: If file does not exist
            json.JSONDecodeError: If file contains malformed JSON
            ValueError: If required fields are missing
        """
        commit_info: CommitInfo | None = None
        add_actions: list[AddAction] = []
        remove_actions: list[RemoveAction] = []

        try:
            # Read file content based on storage type
            if filesystem is not None:
                # Cloud storage - use PyArrow filesystem
                if pafs is None:
                    raise ImportError(
                        "PyArrow is required for cloud storage support. "
                        "Install with: pip install pyarrow"
                    )

                try:
                    with filesystem.open_input_file(file_path) as f:
                        content = f.read().decode("utf-8")
                except FileNotFoundError as e:
                    raise FileNotFoundError(f"Version file not found: {file_path}") from e
            else:
                # Local filesystem
                path = Path(file_path)
                if not path.exists():
                    raise FileNotFoundError(f"Version file not found: {file_path}")

                with open(path, encoding="utf-8") as f:
                    content = f.read()

            # Parse JSON lines
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as e:
                    raise json.JSONDecodeError(
                        f"Malformed JSON in {file_path}: {e.msg}", e.doc, e.pos
                    ) from e

                # Parse commitInfo
                if "commitInfo" in entry:
                    commit_data = entry["commitInfo"]
                    commit_info = CommitInfo(
                        timestamp=commit_data.get("timestamp", 0),
                        operation=commit_data.get("operation", "UNKNOWN"),
                        operation_parameters=commit_data.get("operationParameters", {}),
                        operation_metrics=commit_data.get("operationMetrics", {}),
                        user_metadata=commit_data.get("userMetadata"),
                        engine_info=commit_data.get("engineInfo"),
                    )

                # Parse add action
                elif "add" in entry:
                    add_data = entry["add"]
                    stats_str = add_data.get("stats")
                    stats = None
                    if stats_str:
                        try:
                            parsed_stats = json.loads(stats_str)
                            # Validate that stats is a dict, not a primitive type
                            if isinstance(parsed_stats, dict):
                                stats = parsed_stats
                            else:
                                logger.warning(
                                    f"Invalid stats type in add action in {file_path}: "
                                    f"expected dict, got {type(parsed_stats).__name__}"
                                )
                        except json.JSONDecodeError as e:
                            raise ValueError(
                                f"Malformed stats JSON in add action in {file_path}: {e.msg}"
                            ) from e

                    add_action = AddAction(
                        path=add_data["path"],
                        size=add_data["size"],
                        modification_time=add_data.get("modificationTime", 0),
                        data_change=add_data.get("dataChange", True),
                        stats=stats,
                        partition_values=add_data.get("partitionValues", {}),
                    )
                    add_actions.append(add_action)

                # Parse remove action
                elif "remove" in entry:
                    remove_data = entry["remove"]
                    remove_action = RemoveAction(
                        path=remove_data["path"],
                        deletion_timestamp=remove_data.get("deletionTimestamp", 0),
                        data_change=remove_data.get("dataChange", True),
                        size=remove_data.get("size"),
                    )
                    remove_actions.append(remove_action)

        except Exception as e:
            if isinstance(e, FileNotFoundError | json.JSONDecodeError):
                raise
            raise ValueError(f"Error parsing version file {file_path}: {str(e)}") from e

        return {
            "commit_info": commit_info,
            "add_actions": add_actions,
            "remove_actions": remove_actions,
        }

    @staticmethod
    def extract_operation_metrics(commit_info: dict[str, Any]) -> dict[str, Any]:
        """Extract and normalize operation metrics.

        Handles different metric formats from various engines (Spark, delta-rs, Databricks).

        Args:
            commit_info: Raw commit info dictionary

        Returns:
            Normalized metrics dictionary with standardized metric names
        """
        metrics = commit_info.get("operationMetrics", {})

        # Normalize common metrics
        normalized: dict[str, Any] = {}

        # File metrics (common across operations)
        if "numFiles" in metrics:
            normalized["num_files"] = metrics["numFiles"]
        if "numAddedFiles" in metrics:
            normalized["num_added_files"] = metrics["numAddedFiles"]
        if "numRemovedFiles" in metrics:
            normalized["num_removed_files"] = metrics["numRemovedFiles"]

        # Row metrics (common across operations)
        if "numOutputRows" in metrics:
            normalized["num_output_rows"] = metrics["numOutputRows"]
        if "numTargetRowsInserted" in metrics:
            normalized["num_target_rows_inserted"] = metrics["numTargetRowsInserted"]
        if "numTargetRowsUpdated" in metrics:
            normalized["num_target_rows_updated"] = metrics["numTargetRowsUpdated"]
        if "numTargetRowsDeleted" in metrics:
            normalized["num_target_rows_deleted"] = metrics["numTargetRowsDeleted"]

        # Byte metrics (common across operations)
        if "numOutputBytes" in metrics:
            normalized["num_output_bytes"] = metrics["numOutputBytes"]
        if "numBytesAdded" in metrics:
            normalized["num_bytes_added"] = metrics["numBytesAdded"]
        if "numBytesRemoved" in metrics:
            normalized["num_bytes_removed"] = metrics["numBytesRemoved"]

        # MERGE-specific metrics
        if "numTargetRowsMatchedUpdated" in metrics:
            normalized["num_target_rows_matched_updated"] = metrics["numTargetRowsMatchedUpdated"]
        if "numTargetRowsMatchedDeleted" in metrics:
            normalized["num_target_rows_matched_deleted"] = metrics["numTargetRowsMatchedDeleted"]
        if "numTargetRowsNotMatchedBySourceUpdated" in metrics:
            normalized["num_target_rows_not_matched_by_source_updated"] = metrics[
                "numTargetRowsNotMatchedBySourceUpdated"
            ]
        if "numTargetRowsNotMatchedBySourceDeleted" in metrics:
            normalized["num_target_rows_not_matched_by_source_deleted"] = metrics[
                "numTargetRowsNotMatchedBySourceDeleted"
            ]
        if "numSourceRows" in metrics:
            normalized["num_source_rows"] = metrics["numSourceRows"]
        if "numTargetFilesAdded" in metrics:
            normalized["num_target_files_added"] = metrics["numTargetFilesAdded"]
        if "numTargetFilesRemoved" in metrics:
            normalized["num_target_files_removed"] = metrics["numTargetFilesRemoved"]
        if "numTargetRowsCopied" in metrics:
            normalized["num_target_rows_copied"] = metrics["numTargetRowsCopied"]

        # DELETE-specific metrics
        if "numDeletedRows" in metrics:
            normalized["num_deleted_rows"] = metrics["numDeletedRows"]
        if "numCopiedRows" in metrics:
            normalized["num_copied_rows"] = metrics["numCopiedRows"]

        # VACUUM-specific metrics
        if "numFilesToDelete" in metrics:
            normalized["num_files_to_delete"] = metrics["numFilesToDelete"]
        if "sizeOfDataToDelete" in metrics:
            normalized["size_of_data_to_delete"] = metrics["sizeOfDataToDelete"]
        if "numDeletedFiles" in metrics:
            normalized["num_deleted_files"] = metrics["numDeletedFiles"]

        # OPTIMIZE-specific metrics
        if "minFileSize" in metrics:
            normalized["min_file_size"] = metrics["minFileSize"]
        if "maxFileSize" in metrics:
            normalized["max_file_size"] = metrics["maxFileSize"]
        if "totalFiles" in metrics:
            normalized["total_files"] = metrics["totalFiles"]
        if "totalSize" in metrics:
            normalized["total_size"] = metrics["totalSize"]

        return normalized
