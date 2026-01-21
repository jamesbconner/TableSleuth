"""Delta Lake adapter using delta-rs library.

This module provides a TableFormatAdapter implementation for Delta Lake tables,
supporting path-based table access from local filesystem and cloud storage.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from deltalake import DeltaTable

from tablesleuth.models import FileRef, SnapshotInfo, TableHandle

from .delta_log_parser import AddAction, DeltaLogParser

try:
    from pyarrow import fs as pafs
except ImportError:
    pafs = None

logger = logging.getLogger(__name__)


class DeltaAdapter:
    """Delta Lake adapter using delta-rs library.

    Supports path-based table access from local filesystem and cloud storage.
    Provides forensic analysis capabilities including version history, file
    analysis, and optimization recommendations.
    """

    def __init__(self, storage_options: dict[str, str] | None = None) -> None:
        """Initialize adapter with optional storage options.

        Args:
            storage_options: Cloud storage credentials and configuration
                Examples:
                - S3: {"AWS_ACCESS_KEY_ID": "...", "AWS_SECRET_ACCESS_KEY": "..."}
                - Azure: {"AZURE_STORAGE_ACCOUNT_NAME": "...", "AZURE_STORAGE_ACCOUNT_KEY": "..."}
        """
        self.storage_options = storage_options or {}

    def _get_filesystem_and_path(self, table_uri: str) -> tuple[pafs.FileSystem | None, str]:
        """Get PyArrow filesystem and normalized path for a table URI.

        Args:
            table_uri: Table URI (local path or cloud URI like s3://bucket/path)

        Returns:
            Tuple of (filesystem, normalized_path)
            - filesystem: PyArrow filesystem for cloud storage, None for local
            - normalized_path: Normalized path component

        Raises:
            ImportError: If PyArrow is not installed for cloud storage
        """
        # Check if this is a cloud URI
        is_cloud = table_uri.startswith(("s3://", "gs://", "abfs://", "abfss://"))

        if is_cloud:
            # Cloud storage - create PyArrow filesystem
            if pafs is None:
                raise ImportError(
                    "PyArrow is required for cloud storage support. "
                    "Install with: pip install pyarrow"
                )

            # Create filesystem from URI and storage options
            filesystem, path = pafs.FileSystem.from_uri(table_uri)

            # Apply storage options if provided
            if self.storage_options:
                # Convert storage options to PyArrow format
                if table_uri.startswith("s3://"):
                    # S3 filesystem
                    s3_options = {}
                    if "AWS_ACCESS_KEY_ID" in self.storage_options:
                        s3_options["access_key"] = self.storage_options["AWS_ACCESS_KEY_ID"]
                    if "AWS_SECRET_ACCESS_KEY" in self.storage_options:
                        s3_options["secret_key"] = self.storage_options["AWS_SECRET_ACCESS_KEY"]
                    if "AWS_REGION" in self.storage_options:
                        s3_options["region"] = self.storage_options["AWS_REGION"]
                    if "AWS_ENDPOINT_URL" in self.storage_options:
                        s3_options["endpoint_override"] = self.storage_options["AWS_ENDPOINT_URL"]

                    if s3_options:
                        filesystem = pafs.S3FileSystem(**s3_options)

            return filesystem, path
        else:
            # Local filesystem - handle file:// prefix
            if table_uri.startswith("file:///"):
                table_uri = table_uri[8:]
            elif table_uri.startswith("file://"):
                table_uri = table_uri[7:]
                # Ensure absolute path for macOS (doesn't contain : for Windows drive)
                if not table_uri.startswith(("/", "\\")) and ":" not in table_uri:
                    table_uri = "/" + table_uri
            elif table_uri.startswith("file:\\"):
                table_uri = table_uri[6:].lstrip("\\")

            # Ensure absolute path for macOS (doesn't contain : for Windows drive)
            if not table_uri.startswith(("/", "\\")) and ":" not in table_uri:
                table_uri = "/" + table_uri

            return None, table_uri

    def _is_delta_table(self, path: str) -> bool:
        """Check if path contains a valid Delta table.

        Validates presence of _delta_log directory and at least one version file.

        Args:
            path: Path to check

        Returns:
            True if path contains a valid Delta table, False otherwise
        """
        try:
            table_path = Path(path)

            # Check if path exists
            if not table_path.exists():
                return False

            # Check for _delta_log directory
            delta_log_path = table_path / "_delta_log"
            if not delta_log_path.exists() or not delta_log_path.is_dir():
                return False

            # Check for at least one version file (00000000000000000000.json)
            version_files = list(delta_log_path.glob("*.json"))
            if not version_files:
                return False

            return True
        except Exception as e:
            logger.debug(f"Error checking if path is Delta table: {e}")
            return False

    def open_table(self, identifier: str, catalog_name: str | None = None) -> TableHandle:
        """Open a Delta table from path.

        Args:
            identifier: Path to Delta table (local or cloud)
                Examples:
                - Local: "./data/my_table/"
                - S3: "s3://bucket/warehouse/events/"
            catalog_name: Optional catalog name (unused in Phase 1)

        Returns:
            TableHandle wrapping DeltaTable instance

        Raises:
            ValueError: If path is not a valid Delta table
            FileNotFoundError: If path does not exist
        """
        # Check if path exists and is valid (for local paths only)
        is_cloud_path = identifier.startswith(("s3://", "gs://", "abfs://", "abfss://"))

        if not is_cloud_path:
            # For local paths, validate before attempting to open
            if not Path(identifier).exists():
                raise FileNotFoundError(
                    f"Table path not found: {identifier}\nVerify the path exists and is accessible."
                )

            # Validate it's a Delta table
            if not self._is_delta_table(identifier):
                raise ValueError(
                    f"Not a valid Delta table: {identifier}\n"
                    f"Expected _delta_log directory not found.\n"
                    f"Verify the path points to a Delta table root directory."
                )

        try:
            # Open the Delta table (delta-rs will validate cloud paths)
            dt = DeltaTable(identifier, storage_options=self.storage_options)
            return TableHandle(native=dt, format_name="delta")
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Table path not found: {identifier}\n"
                f"Verify the path exists and is accessible.\n"
                f"Error: {str(e)}"
            ) from e
        except Exception as e:
            # Check if it's a "not a Delta table" error
            error_msg = str(e).lower()
            if "not a delta table" in error_msg or "_delta_log" in error_msg:
                raise ValueError(
                    f"Not a valid Delta table: {identifier}\n"
                    f"Expected _delta_log directory not found.\n"
                    f"Verify the path points to a Delta table root directory.\n"
                    f"Error: {str(e)}"
                ) from e
            raise ValueError(f"Failed to open Delta table: {identifier}\nError: {str(e)}") from e

    def list_snapshots(self, table: TableHandle) -> list[SnapshotInfo]:
        """List all versions (snapshots) of the Delta table.

        Args:
            table: TableHandle containing DeltaTable

        Returns:
            List of SnapshotInfo for each version (0 to current)
        """
        dt: DeltaTable = table.native
        current_version = dt.version()

        snapshots: list[SnapshotInfo] = []
        for version in range(current_version + 1):
            try:
                snapshot = self._build_snapshot_info(dt, version)
                snapshots.append(snapshot)
            except Exception as e:
                logger.warning(f"Failed to load version {version}: {e}")
                continue

        return snapshots

    def load_snapshot(self, table: TableHandle, snapshot_id: int | None) -> SnapshotInfo:
        """Load a specific version of the Delta table.

        Args:
            table: TableHandle containing DeltaTable
            snapshot_id: Version number (None for current version)

        Returns:
            SnapshotInfo for the specified version

        Raises:
            ValueError: If version number is out of range
        """
        dt: DeltaTable = table.native

        # Get the maximum version by loading the latest version first
        # This ensures we know the full version range
        if not hasattr(table, "_max_version"):
            # Store the max version on first call
            table._max_version = dt.version()  # type: ignore[attr-defined]

        current_version = table._max_version  # type: ignore[attr-defined]

        # Use current version if not specified
        if snapshot_id is None:
            snapshot_id = current_version

        # Validate version range
        if snapshot_id < 0 or snapshot_id > current_version:
            raise ValueError(
                f"Version {snapshot_id} is out of range.\n"
                f"Valid versions: 0 to {current_version}\n"
                f"Use --version option to specify a valid version."
            )

        # Load the table at the specified version
        # Note: This modifies the DeltaTable object to point to the specified version
        if dt.version() != snapshot_id:
            dt.load_as_version(snapshot_id)

        return self._build_snapshot_info(dt, snapshot_id)

    def iter_data_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]:
        """Iterate over data files in the snapshot.

        Args:
            snapshot: SnapshotInfo containing file references

        Returns:
            Iterator of FileRef objects for data files
        """
        return iter(snapshot.data_files)

    def iter_delete_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]:
        """Iterate over delete files in the snapshot.

        Note: Delta Lake doesn't have separate delete files like Iceberg.
        Delete operations are tracked in the transaction log.

        Args:
            snapshot: SnapshotInfo containing file references

        Returns:
            Empty iterator (Delta has no separate delete files)
        """
        return iter([])

    def _build_snapshot_info(self, dt: DeltaTable, version: int) -> SnapshotInfo:
        """Build SnapshotInfo from Delta table version.

        Extracts:
        - Version number (maps to snapshot_id)
        - Timestamp from commit info
        - Operation type (WRITE, MERGE, UPDATE, DELETE, OPTIMIZE, VACUUM)
        - Operation metrics (rows, bytes, files)
        - Data files (add actions accumulated from version 0 to target version)
        - User metadata and attribution

        Args:
            dt: DeltaTable instance (already loaded at the target version)
            version: Version number

        Returns:
            SnapshotInfo for the version
        """
        # Get the transaction log path for reading commit info
        table_uri = dt.table_uri

        # Get filesystem and normalized path
        filesystem, table_path = self._get_filesystem_and_path(table_uri)

        # Build delta log path
        if filesystem is not None:
            # Cloud storage - use forward slashes
            delta_log_path_str = f"{table_path}/_delta_log"
            version_file = f"{delta_log_path_str}/{version:020d}.json"
            delta_log_path: Path | None = None
        else:
            # Local filesystem
            delta_log_path = Path(table_path) / "_delta_log"
            delta_log_path_str = str(delta_log_path)
            version_file = str(delta_log_path / f"{version:020d}.json")

        # Parse the current version file for commit info
        parsed = DeltaLogParser.parse_version_file(version_file, filesystem)
        commit_info = parsed["commit_info"]

        # Build summary dictionary from current version
        summary: dict[str, str] = {}
        if commit_info:
            summary["operation"] = commit_info.operation
            summary["timestamp"] = str(commit_info.timestamp)

            # Add operation parameters
            for key, value in commit_info.operation_parameters.items():
                summary[f"param_{key}"] = str(value)

            # Add operation metrics
            for key, value in commit_info.operation_metrics.items():
                summary[f"metric_{key}"] = str(value)

            # Add user metadata
            if commit_info.user_metadata:
                summary["userMetadata"] = commit_info.user_metadata
            if commit_info.engine_info:
                summary["engineInfo"] = commit_info.engine_info

        # Accumulate all active files from version 0 to target version
        # This gives us the complete state of the table at this version
        active_files: dict[str, AddAction] = {}  # path -> AddAction

        for v in range(version + 1):
            if filesystem is not None:
                # Cloud storage
                v_file = f"{delta_log_path_str}/{v:020d}.json"
            else:
                # Local filesystem
                assert delta_log_path is not None
                v_file = str(delta_log_path / f"{v:020d}.json")

            try:
                v_parsed = DeltaLogParser.parse_version_file(v_file, filesystem)

                # Add new files
                for add_action in v_parsed["add_actions"]:
                    active_files[add_action.path] = add_action

                # Remove deleted files
                for remove_action in v_parsed["remove_actions"]:
                    if remove_action.path in active_files:
                        del active_files[remove_action.path]

            except FileNotFoundError:
                # Version file doesn't exist, skip
                continue
            except Exception as e:
                logger.warning(f"Failed to parse version {v}: {e}")
                continue

        # Convert accumulated add actions to FileRef objects
        data_files = [self._create_file_ref(action, table_path) for action in active_files.values()]

        # Determine operation type
        operation = commit_info.operation if commit_info else "UNKNOWN"

        # Determine timestamp
        timestamp_ms = commit_info.timestamp if commit_info else 0

        return SnapshotInfo(
            snapshot_id=version,
            parent_id=version - 1 if version > 0 else None,
            timestamp_ms=timestamp_ms,
            operation=operation,
            summary=summary,
            data_files=data_files,
            delete_files=[],  # Delta doesn't have separate delete files
        )

    def _create_file_ref(self, add_action: AddAction, table_uri: str) -> FileRef:
        """Create FileRef from add action.

        Args:
            add_action: AddAction from transaction log
            table_uri: Base URI of the table

        Returns:
            FileRef object
        """
        # Parse stats if available
        stats = add_action.stats or {}
        record_count = stats.get("numRecords")

        # Construct full path by joining table URI with relative file path
        # The add_action.path is relative to the table root
        full_path = str(Path(table_uri) / add_action.path)

        return FileRef(
            path=full_path,
            file_size_bytes=add_action.size,
            record_count=record_count,
            source="delta",
            content_type="DATA",
            partition=add_action.partition_values,
            sequence_number=None,  # Delta doesn't use sequence numbers
            data_sequence_number=None,
            extra={
                "modification_time": add_action.modification_time,
                "data_change": add_action.data_change,
                "stats": stats,
            },
        )

    def get_schema_at_version(self, table: TableHandle, version: int) -> dict[str, str]:
        """Get the schema at a specific version.

        Delta Lake only writes metaData entries when the schema changes, typically
        in version 0. This method searches backwards from the requested version to
        find the most recent metaData entry.

        Args:
            table: TableHandle containing DeltaTable
            version: Version number to get schema for

        Returns:
            Dictionary mapping column names to data types

        Raises:
            ValueError: If version number is out of range or no schema found
        """
        dt: DeltaTable = table.native
        table_uri = dt.table_uri

        # Get filesystem and normalized path
        filesystem, table_path = self._get_filesystem_and_path(table_uri)

        # Build delta log path
        if filesystem is not None:
            # Cloud storage
            delta_log_path_str = f"{table_path}/_delta_log"
            version_file = f"{delta_log_path_str}/{version:020d}.json"
            delta_log_path: Path | None = None
        else:
            # Local filesystem
            delta_log_path = Path(table_path) / "_delta_log"
            delta_log_path_str = str(delta_log_path)
            version_file = str(delta_log_path / f"{version:020d}.json")

        # Check if version file exists
        try:
            DeltaLogParser.parse_version_file(version_file, filesystem)
        except FileNotFoundError:
            # Try to determine the max version
            if filesystem is not None:
                # Cloud storage - list files
                try:
                    file_info = filesystem.get_file_info(pafs.FileSelector(delta_log_path_str))
                    version_files = [
                        f.path
                        for f in file_info
                        if f.path.endswith(".json")
                        and "checkpoint" not in f.path
                        and f.path.split("/")[-1].split(".")[0].isdigit()
                    ]
                except Exception:
                    version_files = []
            else:
                # Local filesystem
                assert delta_log_path is not None
                version_files_list = list(delta_log_path.glob("*.json"))
                version_files = [str(f) for f in version_files_list if f.stem.isdigit()]

            if version_files:
                if filesystem is not None:
                    max_version = max(int(f.split("/")[-1].split(".")[0]) for f in version_files)
                else:
                    max_version = max(int(f.stem) for f in version_files)
                raise ValueError(
                    f"Version {version} is out of range.\nValid versions: 0 to {max_version}"
                ) from None
            else:
                raise ValueError(
                    f"Version {version} is out of range.\nNo version files found"
                ) from None

        # Search backwards from requested version to find most recent metaData entry
        schema_dict: dict[str, str] = {}

        for v in range(version, -1, -1):
            if filesystem is not None:
                v_file = f"{delta_log_path_str}/{v:020d}.json"
            else:
                assert delta_log_path is not None
                v_file = str(delta_log_path / f"{v:020d}.json")

            try:
                parsed = DeltaLogParser.parse_version_file(v_file, filesystem)

                # Check if this version has metadata by parsing the file again for metaData entry
                # (DeltaLogParser doesn't extract metaData, only commitInfo/add/remove)
                if filesystem is not None:
                    with filesystem.open_input_file(v_file) as f:
                        content = f.read().decode("utf-8")
                else:
                    with open(v_file, encoding="utf-8") as f:
                        content = f.read()

                for line in content.splitlines():
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        entry = json.loads(line)

                        # Look for metaData entry
                        if "metaData" in entry:
                            metadata = entry["metaData"]
                            schema_string = metadata.get("schemaString", "{}")
                            schema_json = json.loads(schema_string)

                            # Extract fields from schema
                            fields = schema_json.get("fields", [])
                            for field in fields:
                                field_name = field["name"]
                                field_type = field["type"]

                                # Handle complex types (struct, array, map)
                                if isinstance(field_type, dict):
                                    field_type = field_type.get("type", str(field_type))

                                schema_dict[field_name] = str(field_type)

                            # Found schema, return immediately
                            logger.debug(
                                f"Found schema at version {v} for requested version {version}: "
                                f"{len(schema_dict)} columns"
                            )
                            return schema_dict

                    except json.JSONDecodeError:
                        continue

            except FileNotFoundError:
                continue
            except Exception as e:
                logger.warning(f"Failed to parse version {v} for schema: {e}")
                continue

        # If we get here, no schema was found in any version
        logger.warning(f"No schema found for version {version} (searched back to version 0)")
        return schema_dict

    def compare_schemas(
        self, old_schema: dict[str, str], new_schema: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Compare two schemas and detect changes.

        Args:
            old_schema: Schema from earlier version (column name -> type)
            new_schema: Schema from later version (column name -> type)

        Returns:
            List of schema change records, each containing:
            - change_type: "column_added", "column_removed", or "type_changed"
            - column_name: Name of the affected column
            - old_type: Previous data type (None for additions)
            - new_type: New data type (None for removals)
            - is_breaking: Whether this is a potentially breaking change
        """
        changes: list[dict[str, Any]] = []

        # Detect removed columns
        for col_name in old_schema:
            if col_name not in new_schema:
                changes.append(
                    {
                        "change_type": "column_removed",
                        "column_name": col_name,
                        "old_type": old_schema[col_name],
                        "new_type": None,
                        "is_breaking": True,  # Column removals are potentially breaking
                    }
                )

        # Detect added columns and type changes
        for col_name in new_schema:
            if col_name not in old_schema:
                # Column added
                changes.append(
                    {
                        "change_type": "column_added",
                        "column_name": col_name,
                        "old_type": None,
                        "new_type": new_schema[col_name],
                        "is_breaking": False,
                    }
                )
            elif old_schema[col_name] != new_schema[col_name]:
                # Type changed
                changes.append(
                    {
                        "change_type": "type_changed",
                        "column_name": col_name,
                        "old_type": old_schema[col_name],
                        "new_type": new_schema[col_name],
                        "is_breaking": False,  # Type changes may or may not be breaking
                    }
                )

        return changes

    def get_versions_with_metadata(self, table: TableHandle) -> set[int]:
        """Get set of version numbers that have metaData entries (schema changes).

        Args:
            table: TableHandle containing DeltaTable

        Returns:
            Set of version numbers that contain metaData entries
        """
        dt: DeltaTable = table.native

        # Get the table URI to find all version files
        table_uri = dt.table_uri

        # Handle file URI prefix
        if table_uri.startswith("file:///"):
            table_uri = table_uri[8:]
        elif table_uri.startswith("file://"):
            table_uri = table_uri[7:]
            # Ensure we have an absolute path (macOS sometimes returns paths without leading /)
            # Only prepend / if it's not a Windows path (doesn't contain : for drive letter)
            if not table_uri.startswith(("/", "\\")) and ":" not in table_uri:
                table_uri = "/" + table_uri
        elif table_uri.startswith("file:\\"):
            table_uri = table_uri[6:].lstrip("\\")

        # Ensure we have an absolute path (macOS sometimes returns paths without leading /)
        # Only prepend / if it's not a Windows path (doesn't contain : for drive letter)
        if not table_uri.startswith(("/", "\\")) and ":" not in table_uri:
            table_uri = "/" + table_uri

        delta_log_path = Path(table_uri) / "_delta_log"

        # Find all version files
        version_files = list(delta_log_path.glob("[0-9]*.json"))
        if not version_files:
            return set()

        current_version = max(int(f.stem) for f in version_files if f.stem.isdigit())

        versions_with_metadata: set[int] = set()

        # Scan each version file for metaData entries
        for version in range(current_version + 1):
            version_file = delta_log_path / f"{version:020d}.json"

            if not version_file.exists():
                continue

            try:
                with open(version_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            if "metaData" in entry:
                                versions_with_metadata.add(version)
                                break  # Found metaData, move to next version
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.warning(f"Failed to scan version {version} for metaData: {e}")
                continue

        return versions_with_metadata

    def get_schema_evolution(self, table: TableHandle) -> list[dict[str, Any]]:
        """Build schema evolution timeline across all versions.

        This method efficiently detects schema changes by scanning for metaData entries
        in the transaction log. Delta Lake only writes metaData when:
        1. The table is created (version 0)
        2. The schema is explicitly changed (ALTER TABLE, schema_mode="merge", etc.)

        Args:
            table: TableHandle containing DeltaTable

        Returns:
            List of schema evolution records, each containing:
            - version: Version number where change occurred
            - changes: List of schema changes at this version
            - timestamp_ms: Timestamp of the version
        """
        dt: DeltaTable = table.native

        # Get the table URI to find all version files
        table_uri = dt.table_uri

        # Handle file URI prefix
        if table_uri.startswith("file:///"):
            table_uri = table_uri[8:]
        elif table_uri.startswith("file://"):
            table_uri = table_uri[7:]
            # Ensure we have an absolute path (macOS sometimes returns paths without leading /)
            # Only prepend / if it's not a Windows path (doesn't contain : for drive letter)
            if not table_uri.startswith(("/", "\\")) and ":" not in table_uri:
                table_uri = "/" + table_uri
        elif table_uri.startswith("file:\\"):
            table_uri = table_uri[6:].lstrip("\\")

        # Ensure we have an absolute path (macOS sometimes returns paths without leading /)
        # Only prepend / if it's not a Windows path (doesn't contain : for drive letter)
        if not table_uri.startswith(("/", "\\")) and ":" not in table_uri:
            table_uri = "/" + table_uri

        delta_log_path = Path(table_uri) / "_delta_log"

        # Find all version files to determine max version
        version_files = list(delta_log_path.glob("[0-9]*.json"))
        if not version_files:
            return []

        current_version = max(int(f.stem) for f in version_files if f.stem.isdigit())

        evolution: list[dict[str, Any]] = []
        previous_schema: dict[str, str] | None = None

        # Scan each version file for metaData entries (schema changes)
        for version in range(current_version + 1):
            version_file = delta_log_path / f"{version:020d}.json"

            if not version_file.exists():
                continue

            # Look for metaData entry in this version
            schema_dict: dict[str, str] = {}
            has_metadata = False

            try:
                with open(version_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())

                            # Look for metaData entry (indicates schema change)
                            if "metaData" in entry:
                                has_metadata = True
                                metadata = entry["metaData"]
                                schema_string = metadata.get("schemaString", "{}")
                                schema_json = json.loads(schema_string)

                                # Extract fields from schema
                                fields = schema_json.get("fields", [])
                                for field in fields:
                                    field_name = field["name"]
                                    field_type = field["type"]

                                    # Handle complex types (struct, array, map)
                                    if isinstance(field_type, dict):
                                        field_type = field_type.get("type", str(field_type))

                                    schema_dict[field_name] = str(field_type)

                                break  # Found metaData, no need to continue

                        except json.JSONDecodeError:
                            continue

                # If we found a metaData entry, this version has a schema change
                if has_metadata and schema_dict:
                    # Compare with previous schema (if any)
                    if previous_schema is not None:
                        changes = self.compare_schemas(previous_schema, schema_dict)

                        if changes:
                            # Get timestamp for this version
                            snapshot = self._build_snapshot_info(dt, version)

                            evolution.append(
                                {
                                    "version": version,
                                    "changes": changes,
                                    "timestamp_ms": snapshot.timestamp_ms,
                                }
                            )
                    else:
                        # Version 0 - initial schema (no changes to report)
                        logger.debug(
                            f"Version {version}: Initial schema with {len(schema_dict)} columns"
                        )

                    # Update previous schema for next iteration
                    previous_schema = schema_dict

            except Exception as e:
                logger.warning(f"Failed to parse version {version} for schema evolution: {e}")
                continue

        return evolution
