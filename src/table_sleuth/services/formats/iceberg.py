from __future__ import annotations

from collections.abc import Iterable
from typing import Optional
from urllib.parse import unquote, urlparse

from pyiceberg.catalog import load_catalog
from pyiceberg.table import Snapshot, StaticTable, Table

from table_sleuth.models import FileRef, SnapshotInfo, TableHandle

from .base import TableFormatAdapter


class IcebergAdapter(TableFormatAdapter):
    """Apache Iceberg adapter using PyIceberg."""

    def __init__(self, default_catalog: Optional[str] = None) -> None:
        self._default_catalog = default_catalog

    def _file_uri_to_path(self, uri: str) -> str:
        """Convert file:// URI to local file path.

        Handles both Unix (file:///path) and Windows (file:///C:/path) URIs correctly.

        Args:
            uri: File URI string

        Returns:
            Local file path
        """
        if not uri.startswith("file://"):
            return uri

        # Parse the URI
        parsed = urlparse(uri)
        # Get the path component and decode any percent-encoded characters
        path = unquote(parsed.path)

        # On Windows, urlparse returns /C:/path, we need to remove the leading /
        # On Unix, urlparse returns /path, which is correct
        if len(path) > 2 and path[0] == "/" and path[2] == ":":
            # Windows path: /C:/path -> C:/path
            return path[1:]

        return path

    def _open_via_catalog(self, identifier: str, catalog_name: str) -> Table:
        catalog = load_catalog(catalog_name)
        return catalog.load_table(identifier)

    def _open_via_metadata_path(self, identifier: str) -> Table:
        return StaticTable.from_metadata(identifier)

    def open_table(self, identifier: str, catalog_name: Optional[str] = None) -> TableHandle:
        if catalog_name:
            table = self._open_via_catalog(identifier, catalog_name)
        elif self._default_catalog:
            table = self._open_via_catalog(identifier, self._default_catalog)
        else:
            table = self._open_via_metadata_path(identifier)
        return TableHandle(native=table, format_name="iceberg")

    def list_snapshots(self, table: TableHandle) -> list[SnapshotInfo]:
        py_table: Table = table.native
        return [self._build_snapshot_info(py_table, s) for s in py_table.snapshots()]

    def load_snapshot(self, table: TableHandle, snapshot_id: Optional[int]) -> SnapshotInfo:
        py_table: Table = table.native
        if snapshot_id is None:
            snapshot = py_table.current_snapshot()
        else:
            snapshot = next(s for s in py_table.snapshots() if s.snapshot_id == snapshot_id)

        if snapshot is None:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        return self._build_snapshot_info(py_table, snapshot)

    def iter_data_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]:
        return (f for f in snapshot.data_files)

    def iter_delete_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]:
        return (f for f in snapshot.delete_files)

    def get_data_files(
        self, table_identifier: str, catalog_name: str | None = None
    ) -> list[FileRef]:
        """Get all data files from an Iceberg table's current snapshot.

        This method is used for MVP 0 to discover Parquet files from Iceberg tables
        without exposing full snapshot/delete file functionality.

        Args:
            table_identifier: Table identifier (e.g., "db.table")
            catalog_name: Catalog name (uses default if None)

        Returns:
            List of FileRef objects for data files with source="iceberg"

        Raises:
            Exception: If catalog or table cannot be loaded
        """
        # Open the table
        table_handle = self.open_table(table_identifier, catalog_name)
        py_table: Table = table_handle.native

        # Get current snapshot
        snapshot = py_table.current_snapshot()
        if snapshot is None:
            return []

        # Extract data files only (ignore delete files for MVP 0)
        data_files: list[FileRef] = []
        scan = py_table.scan(snapshot_id=snapshot.snapshot_id)

        for file_task in scan.plan_files():
            f = file_task.file

            # DataFile objects are data files (delete files would be DeleteFile)
            # For MVP 0, we only want data files
            # Convert file:// URI to regular path
            file_path = self._file_uri_to_path(f.file_path)

            # Convert partition Record to dict - use vars() to get dict representation
            partition_dict: dict[str, str] = {}
            if f.partition is not None:
                try:
                    # Try to convert Record to dict using vars or dict()
                    partition_dict = {str(k): str(v) for k, v in vars(f.partition).items()}
                except (TypeError, AttributeError):
                    # Fallback if vars() doesn't work
                    partition_dict = {}

            ref = FileRef(
                path=file_path,
                file_size_bytes=f.file_size_in_bytes,
                record_count=f.record_count,
                source="iceberg",
                content_type="DATA",
                partition=partition_dict,
                sequence_number=None,  # Not available in this API version
                data_sequence_number=None,  # Not available in this API version
                extra={
                    "spec_id": f.spec_id,
                    "sort_order_id": getattr(f, "sort_order_id", None),
                },
            )
            data_files.append(ref)

        return data_files

    def _build_snapshot_info(self, table: Table, snapshot: Snapshot) -> SnapshotInfo:
        data_files: list[FileRef] = []
        delete_files: list[FileRef] = []

        scan = table.scan(snapshot_id=snapshot.snapshot_id)
        for file_task in scan.plan_files():
            f = file_task.file

            # Determine content type based on file type
            # DataFile objects are data files, DeleteFile would be delete files
            content_type = "DATA"  # Default for DataFile

            # Convert file:// URI to regular path
            file_path = self._file_uri_to_path(f.file_path)

            # Convert partition Record to dict - use vars() to get dict representation
            partition_dict: dict[str, str] = {}
            if f.partition is not None:
                try:
                    # Try to convert Record to dict using vars or dict()
                    partition_dict = {str(k): str(v) for k, v in vars(f.partition).items()}
                except (TypeError, AttributeError):
                    # Fallback if vars() doesn't work
                    partition_dict = {}

            ref = FileRef(
                path=file_path,
                file_size_bytes=f.file_size_in_bytes,
                record_count=f.record_count,
                source="iceberg",
                content_type=content_type,
                partition=partition_dict,
                sequence_number=None,  # Not available in this API version
                data_sequence_number=None,  # Not available in this API version
                extra={
                    "spec_id": f.spec_id,
                    "sort_order_id": getattr(f, "sort_order_id", None),
                },
            )

            if content_type == "DATA":
                data_files.append(ref)
            else:
                delete_files.append(ref)

        # Extract operation and summary with proper type handling
        operation_value = getattr(snapshot, "operation", None)
        operation_str = str(operation_value) if operation_value is not None else "unknown"

        # Convert Summary to dict[str, str]
        summary_dict: dict[str, str] = {}
        if snapshot.summary:
            for key in dir(snapshot.summary):
                if not key.startswith("_"):
                    try:
                        value = getattr(snapshot.summary, key)
                        if not callable(value):
                            summary_dict[key] = str(value)
                    except (AttributeError, TypeError):
                        pass

        return SnapshotInfo(
            snapshot_id=snapshot.snapshot_id,
            parent_id=snapshot.parent_snapshot_id,
            timestamp_ms=snapshot.timestamp_ms,
            operation=operation_str,
            summary=summary_dict,
            data_files=data_files,
            delete_files=delete_files,
        )
