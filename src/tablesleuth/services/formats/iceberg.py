from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Optional
from urllib.parse import unquote, urlparse

from pyiceberg.catalog import load_catalog
from pyiceberg.table import Snapshot, StaticTable, Table

from tablesleuth.models import FileRef, SnapshotInfo, TableHandle

from .base import TableFormatAdapter


class IcebergAdapter(TableFormatAdapter):
    """Apache Iceberg adapter using PyIceberg.

    Supports multiple catalog types:
    - Local SQL catalogs
    - AWS S3 Tables via Glue catalog
    - Direct metadata file paths
    """

    # S3 Tables ARN pattern: arn:aws:s3tables:region:account:bucket/bucket-name/table/namespace.table
    # Also supports UUID format: arn:aws:s3tables:region:account:bucket/bucket-name/table/uuid
    S3_TABLES_ARN_PATTERN = re.compile(
        r"arn:aws:s3tables:(?P<region>[^:]+):(?P<account>\d+):"
        r"bucket/(?P<bucket>[^/]+)/table/(?P<table>.+)"
    )

    def __init__(self, default_catalog: str | None = None) -> None:
        self._default_catalog = default_catalog

    def _parse_s3_tables_arn(
        self, arn: str, catalog_name: str | None = None
    ) -> tuple[str, str] | None:
        """Parse S3 Tables ARN into catalog name and table identifier.

        Args:
            arn: S3 Tables ARN (e.g., arn:aws:s3tables:us-east-2:123456:bucket/my-bucket/table/db.table)
            catalog_name: Optional catalog name to use. If not provided, uses "s3tables" as default.

        Returns:
            Tuple of (catalog_name, table_identifier) or None if not an S3 Tables ARN
        """
        match = self.S3_TABLES_ARN_PATTERN.match(arn)
        if not match:
            return None

        # Extract table identifier (namespace.table)
        table_identifier = match.group("table")

        # Use provided catalog name or default to "s3tables"
        catalog = catalog_name if catalog_name else "s3tables"
        return (catalog, table_identifier)

    def _file_uri_to_path(self, uri: str) -> str:
        """Convert file:// URI to local file path, preserve S3 URIs.

        Handles both Unix (file:///path) and Windows (file:///C:/path) URIs correctly.
        S3 URIs (s3://bucket/path) are returned unchanged.

        Args:
            uri: File URI string

        Returns:
            Local file path or S3 URI
        """
        # Preserve S3 URIs unchanged
        if uri.startswith("s3://") or uri.startswith("s3a://"):
            return uri

        # Only convert file:// URIs
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

    def open_table(self, identifier: str, catalog_name: str | None = None) -> TableHandle:
        """Open an Iceberg table from various sources.

        Args:
            identifier: Can be:
                - Table identifier (e.g., "db.table") when using catalog_name
                - S3 Tables ARN (e.g., "arn:aws:s3tables:region:account:bucket/name/table/db.table")
                - Path to metadata.json file
            catalog_name: Optional catalog name to use. For S3 Tables ARNs, this specifies
                which S3 Tables catalog configuration to use.

        Returns:
            TableHandle wrapping the PyIceberg Table
        """
        # Check if identifier is an S3 Tables ARN
        s3_tables_info = self._parse_s3_tables_arn(identifier, catalog_name)
        if s3_tables_info:
            catalog_name, table_identifier = s3_tables_info
            table = self._open_via_catalog(table_identifier, catalog_name)
        elif catalog_name:
            table = self._open_via_catalog(identifier, catalog_name)
        elif self._default_catalog:
            table = self._open_via_catalog(identifier, self._default_catalog)
        else:
            table = self._open_via_metadata_path(identifier)
        return TableHandle(native=table, format_name="iceberg")

    def list_snapshots(self, table: TableHandle) -> list[SnapshotInfo]:
        py_table: Table = table.native
        return [self._build_snapshot_info(py_table, s) for s in py_table.snapshots()]

    def load_snapshot(self, table: TableHandle, snapshot_id: int | None) -> SnapshotInfo:
        py_table: Table = table.native
        if snapshot_id is None:
            snapshot = py_table.current_snapshot()
            if snapshot is None:
                raise ValueError("Table has no current snapshot")
        else:
            snapshot = next((s for s in py_table.snapshots() if s.snapshot_id == snapshot_id), None)
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

        This method discovers Parquet data files from Iceberg tables for inspection.

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

        # Extract data files from current snapshot
        data_files: list[FileRef] = []
        scan = py_table.scan(snapshot_id=snapshot.snapshot_id)

        for file_task in scan.plan_files():
            f = file_task.file
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

        # Convert Summary to dict[str, str] using additional_properties
        summary_dict: dict[str, str] = {}
        if snapshot.summary and hasattr(snapshot.summary, "additional_properties"):
            summary_dict = {
                str(k): str(v) for k, v in snapshot.summary.additional_properties.items()
            }

        return SnapshotInfo(
            snapshot_id=snapshot.snapshot_id,
            parent_id=snapshot.parent_snapshot_id,
            timestamp_ms=snapshot.timestamp_ms,
            operation=operation_str,
            summary=summary_dict,
            data_files=data_files,
            delete_files=delete_files,
        )
