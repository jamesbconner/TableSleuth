"""Service for loading and querying Iceberg table metadata."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pyiceberg.catalog import load_catalog
from pyiceberg.table import StaticTable, Table

from tablesleuth.exceptions import (
    MetadataError,
    SnapshotNotFoundError,
    TableLoadError,
)
from tablesleuth.models.iceberg import (
    IcebergSnapshotDetails,
    IcebergSnapshotInfo,
    IcebergTableInfo,
    PartitionField,
    PartitionSpecInfo,
    SchemaField,
    SchemaInfo,
    SnapshotComparison,
    SortField,
    SortOrderInfo,
)
from tablesleuth.services.formats.iceberg import IcebergAdapter

logger = logging.getLogger(__name__)


class IcebergMetadataService:
    """Service for loading and querying Iceberg table metadata."""

    def __init__(self) -> None:
        """Initialize the Iceberg metadata service."""
        self._adapter = IcebergAdapter()

    def load_table(
        self,
        metadata_path: str | None = None,
        catalog_name: str | None = None,
        table_identifier: str | None = None,
    ) -> IcebergTableInfo:
        """Load an Iceberg table from metadata file or catalog.

        Args:
            metadata_path: Path to metadata JSON file
            catalog_name: Name of catalog to use
            table_identifier: Table identifier (e.g., "db.table")

        Returns:
            IcebergTableInfo object

        Raises:
            TableLoadError: If table cannot be loaded
            ValueError: If invalid arguments provided
        """
        try:
            if metadata_path:
                # Load from metadata file
                metadata_file = Path(metadata_path)
                if not metadata_file.exists():
                    raise TableLoadError(f"Metadata file not found: {metadata_path}")

                try:
                    table: Table = StaticTable.from_metadata(metadata_path)
                    location = metadata_path
                except Exception as e:
                    logger.exception(f"Failed to load table from metadata file: {metadata_path}")
                    raise TableLoadError(f"Failed to load table from metadata file: {e}") from e

            elif catalog_name and table_identifier:
                # Load from catalog
                try:
                    catalog = load_catalog(catalog_name)
                except Exception as e:
                    logger.exception(f"Failed to load catalog: {catalog_name}")
                    raise TableLoadError(f"Failed to load catalog '{catalog_name}': {e}") from e

                try:
                    table = catalog.load_table(table_identifier)
                    location = table.metadata_location
                except Exception as e:
                    logger.exception(
                        f"Failed to load table {table_identifier} from catalog {catalog_name}"
                    )
                    raise TableLoadError(
                        f"Failed to load table '{table_identifier}' from catalog '{catalog_name}': {e}"
                    ) from e
            else:
                raise ValueError(
                    "Must provide either metadata_path or both catalog_name and table_identifier"
                )

            return IcebergTableInfo(
                metadata_location=location,
                format_version=table.metadata.format_version,
                table_uuid=str(table.metadata.table_uuid),
                location=table.metadata.location,
                current_snapshot_id=(
                    current_snap.snapshot_id
                    if (current_snap := table.current_snapshot()) is not None
                    else None
                ),
                properties=dict(table.properties),
                native_table=table,
            )
        except TableLoadError:
            raise
        except ValueError:
            raise
        except Exception as e:
            logger.exception("Unexpected error loading table")
            raise TableLoadError(f"Unexpected error loading table: {e}") from e

    def list_snapshots(self, table: IcebergTableInfo) -> list[IcebergSnapshotInfo]:
        """Get all snapshots for a table.

        Args:
            table: IcebergTableInfo object

        Returns:
            List of IcebergSnapshotInfo objects, sorted by timestamp descending
        """
        py_table: Table = table.native_table
        snapshots = []

        for snapshot in py_table.snapshots():
            # Extract summary statistics
            summary = (
                dict(snapshot.summary.additional_properties)
                if snapshot.summary is not None
                and hasattr(snapshot.summary, "additional_properties")
                else {}
            )

            # Debug: Log summary keys to see what's available
            logger.debug(f"Snapshot {snapshot.snapshot_id} summary keys: {list(summary.keys())}")

            # Get operation from summary or snapshot object
            # Try multiple possible locations for the operation
            operation = summary.get("operation")
            if not operation and hasattr(snapshot, "operation"):
                operation = str(snapshot.operation) if snapshot.operation else None

            # If still no operation, try to infer from summary metrics
            if not operation or operation == "UNKNOWN":
                operation = self._infer_operation(summary)

            logger.debug(f"Snapshot {snapshot.snapshot_id} operation: {operation}")

            # Extract metrics from summary
            total_records = int(summary.get("total-records", 0))
            total_data_files = int(summary.get("total-data-files", 0))
            total_delete_files = int(summary.get("total-delete-files", 0))
            total_size = int(summary.get("total-files-size", 0))
            position_deletes = int(summary.get("total-position-deletes", 0))
            equality_deletes = int(summary.get("total-equality-deletes", 0))

            snapshot_info = IcebergSnapshotInfo(
                snapshot_id=snapshot.snapshot_id,
                parent_snapshot_id=snapshot.parent_snapshot_id,
                timestamp_ms=snapshot.timestamp_ms,
                operation=str(operation),
                summary=summary,
                manifest_list=snapshot.manifest_list,
                schema_id=snapshot.schema_id if snapshot.schema_id is not None else 0,
                total_records=total_records,
                total_data_files=total_data_files,
                total_delete_files=total_delete_files,
                total_size_bytes=total_size,
                position_deletes=position_deletes,
                equality_deletes=equality_deletes,
            )
            snapshots.append(snapshot_info)

        # Sort by timestamp descending (most recent first)
        snapshots.sort(key=lambda s: s.timestamp_ms, reverse=True)

        return snapshots

    def get_snapshot_details(
        self, table: IcebergTableInfo, snapshot_id: int
    ) -> IcebergSnapshotDetails:
        """Get detailed information about a specific snapshot.

        Args:
            table: IcebergTableInfo object
            snapshot_id: Snapshot ID to get details for

        Returns:
            IcebergSnapshotDetails object

        Raises:
            SnapshotNotFoundError: If snapshot not found
            MetadataError: If snapshot metadata cannot be read
        """
        try:
            py_table: Table = table.native_table

            # Find the snapshot
            snapshot = None
            for s in py_table.snapshots():
                if s.snapshot_id == snapshot_id:
                    snapshot = s
                    break

            if snapshot is None:
                raise SnapshotNotFoundError(
                    f"Snapshot {snapshot_id} not found in table {table.table_uuid}"
                )

            # Get snapshot info
            snapshots = self.list_snapshots(table)
            snapshot_info = next((s for s in snapshots if s.snapshot_id == snapshot_id), None)
            if snapshot_info is None:
                raise SnapshotNotFoundError(f"Snapshot {snapshot_id} not found in snapshot list")

            # Scan to get files
            scan = py_table.scan(snapshot_id=snapshot_id)
            data_files: list[dict[str, Any]] = []
            delete_files_dict: dict[str, dict[str, Any]] = {}  # Use dict to deduplicate by path

            for file_task in scan.plan_files():
                f = file_task.file
                file_path = self._adapter._file_uri_to_path(f.file_path)

                # Create file info
                file_info = {
                    "file_path": file_path,
                    "file_size_bytes": f.file_size_in_bytes,
                    "record_count": f.record_count,
                }
                data_files.append(file_info)

                # Get delete files associated with this data file
                # Use dict to avoid duplicates (same delete file can apply to multiple data files)
                if hasattr(file_task, "delete_files") and file_task.delete_files:
                    for delete_file in file_task.delete_files:
                        delete_path = self._adapter._file_uri_to_path(delete_file.file_path)
                        # Only add if not already seen
                        if delete_path not in delete_files_dict:
                            delete_info = {
                                "file_path": delete_path,
                                "file_size_bytes": delete_file.file_size_in_bytes,
                                "record_count": delete_file.record_count,
                                "content": str(delete_file.content)
                                if hasattr(delete_file, "content")
                                else "DELETE",
                            }
                            delete_files_dict[delete_path] = delete_info

            # Convert dict back to list
            delete_files = list(delete_files_dict.values())

            # Get schema
            schema = py_table.schema()
            schema_info = SchemaInfo(
                schema_id=schema.schema_id,
                fields=[
                    SchemaField(
                        field_id=field.field_id,
                        name=field.name,
                        field_type=str(field.field_type),
                        required=field.required,
                        doc=field.doc,
                    )
                    for field in schema.fields
                ],
            )

            # Get partition spec
            spec = py_table.spec()
            partition_spec = PartitionSpecInfo(
                spec_id=spec.spec_id,
                fields=[
                    PartitionField(
                        field_id=field.field_id,
                        source_id=field.source_id,
                        name=field.name,
                        transform=str(field.transform),
                    )
                    for field in spec.fields
                ],
            )

            # Get sort order
            sort_order_obj = py_table.sort_order()
            sort_order = None
            if sort_order_obj.fields:
                sort_order = SortOrderInfo(
                    order_id=sort_order_obj.order_id,
                    fields=[
                        SortField(
                            source_id=field.source_id,
                            transform=str(field.transform),
                            direction=str(field.direction),
                            null_order=str(field.null_order),
                        )
                        for field in sort_order_obj.fields
                    ],
                )

            return IcebergSnapshotDetails(
                snapshot_info=snapshot_info,
                data_files=data_files,
                delete_files=delete_files,
                schema=schema_info,
                partition_spec=partition_spec,
                sort_order=sort_order,
            )
        except SnapshotNotFoundError:
            raise
        except Exception as e:
            logger.exception(f"Failed to get snapshot details for snapshot {snapshot_id}")
            raise MetadataError(
                f"Failed to get snapshot details for snapshot {snapshot_id}: {e}"
            ) from e

    def compare_snapshots(
        self,
        table: IcebergTableInfo,
        snapshot_a_id: int,
        snapshot_b_id: int,
    ) -> SnapshotComparison:
        """Compare two snapshots and calculate differences.

        Args:
            table: IcebergTableInfo object
            snapshot_a_id: First snapshot ID
            snapshot_b_id: Second snapshot ID

        Returns:
            SnapshotComparison object
        """
        # Get snapshot info for both
        snapshots = self.list_snapshots(table)
        snapshot_a = next((s for s in snapshots if s.snapshot_id == snapshot_a_id), None)
        snapshot_b = next((s for s in snapshots if s.snapshot_id == snapshot_b_id), None)

        if snapshot_a is None:
            raise SnapshotNotFoundError(f"Snapshot {snapshot_a_id} not found")
        if snapshot_b is None:
            raise SnapshotNotFoundError(f"Snapshot {snapshot_b_id} not found")

        # Calculate file changes
        data_files_added = snapshot_b.total_data_files - snapshot_a.total_data_files
        data_files_removed = max(0, -data_files_added)
        data_files_added = max(0, data_files_added)

        delete_files_added = snapshot_b.total_delete_files - snapshot_a.total_delete_files
        delete_files_removed = max(0, -delete_files_added)
        delete_files_added = max(0, delete_files_added)

        # Calculate record changes
        records_delta = snapshot_b.total_records - snapshot_a.total_records
        records_added = max(0, records_delta)
        records_deleted = max(0, -records_delta)

        # Calculate size changes
        size_delta = snapshot_b.total_size_bytes - snapshot_a.total_size_bytes
        size_added = max(0, size_delta)
        size_removed = max(0, -size_delta)

        # Calculate MOR metrics changes
        delete_ratio_change = snapshot_b.delete_ratio - snapshot_a.delete_ratio
        read_amp_change = snapshot_b.read_amplification - snapshot_a.read_amplification

        return SnapshotComparison(
            snapshot_a=snapshot_a,
            snapshot_b=snapshot_b,
            data_files_added=data_files_added,
            data_files_removed=data_files_removed,
            delete_files_added=delete_files_added,
            delete_files_removed=delete_files_removed,
            records_added=records_added,
            records_deleted=records_deleted,
            records_delta=records_delta,
            size_added_bytes=size_added,
            size_removed_bytes=size_removed,
            size_delta_bytes=size_delta,
            delete_ratio_change=delete_ratio_change,
            read_amplification_change=read_amp_change,
        )

    def get_schema_evolution(self, table: IcebergTableInfo) -> list[SchemaInfo]:
        """Get schema evolution history.

        Args:
            table: IcebergTableInfo object

        Returns:
            List of SchemaInfo objects, one for each schema version
        """
        py_table: Table = table.native_table
        schemas = []

        for schema in py_table.metadata.schemas:
            schema_info = SchemaInfo(
                schema_id=schema.schema_id,
                fields=[
                    SchemaField(
                        field_id=field.field_id,
                        name=field.name,
                        field_type=str(field.field_type),
                        required=field.required,
                        doc=field.doc,
                    )
                    for field in schema.fields
                ],
            )
            schemas.append(schema_info)

        return schemas

    def _infer_operation(self, summary: dict[str, str]) -> str:
        """Infer operation type from snapshot summary metrics.

        Args:
            summary: Snapshot summary dictionary

        Returns:
            Inferred operation type
        """
        # Check for explicit operation indicators in summary
        added_files = int(summary.get("added-data-files", 0))
        deleted_files = int(summary.get("deleted-data-files", 0))
        added_records = int(summary.get("added-records", 0))
        deleted_records = int(summary.get("deleted-records", 0))
        added_delete_files = int(summary.get("added-delete-files", 0))

        # Infer based on metrics (order matters - check most specific conditions first)
        # Note: Presence of added_delete_files indicates merge-on-read (MOR) operations

        # Merge-on-read UPDATE: delete files + new data files (with or without deletions)
        # This includes compaction scenarios where old files are removed
        if added_delete_files > 0 and added_files > 0:
            return "UPDATE"

        # Merge-on-read DELETE: delete files without adding new data files
        if added_delete_files > 0 and added_files == 0:
            return "DELETE"

        # Copy-on-write operations (no delete files)
        # Distinguish OVERWRITE vs REPLACE by checking if all files were replaced
        if deleted_files > 0 and added_delete_files == 0:
            # If files were both added and deleted, could be OVERWRITE or REPLACE
            # Check for explicit indicators in summary
            if "replaced-partitions" in summary or "partition-summaries" in summary:
                return "REPLACE"
            # If all data files were deleted, it's likely a full OVERWRITE
            total_data_files = int(summary.get("total-data-files", 0))
            if total_data_files == added_files:
                # All current files are new = full overwrite
                return "OVERWRITE"
            # Otherwise, assume REPLACE (partial rewrite)
            if added_files > 0:
                return "REPLACE"
            # Only deletions, no additions
            return "OVERWRITE"

        # APPEND: only files added (most common)
        if added_files > 0:
            return "APPEND"

        # Fallback to record changes
        if added_records > 0 or deleted_records > 0:
            return "UPDATE"

        return "UNKNOWN"
