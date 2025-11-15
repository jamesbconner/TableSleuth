from __future__ import annotations

from collections.abc import Iterable
from typing import Optional

from pyiceberg.catalog import load_catalog
from pyiceberg.table import Snapshot, StaticTable, Table

from table_sleuth.models import FileRef, SnapshotInfo, TableHandle

from .base import TableFormatAdapter


class IcebergAdapter(TableFormatAdapter):
    """Apache Iceberg adapter using PyIceberg."""

    def __init__(self, default_catalog: Optional[str] = None) -> None:
        self._default_catalog = default_catalog

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
        return self._build_snapshot_info(py_table, snapshot)

    def iter_data_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]:
        return (f for f in snapshot.data_files)

    def iter_delete_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]:
        return (f for f in snapshot.delete_files)

    def _build_snapshot_info(self, table: Table, snapshot: Snapshot) -> SnapshotInfo:
        data_files: list[FileRef] = []
        delete_files: list[FileRef] = []

        scan = table.scan().use_snapshot(snapshot.snapshot_id)
        for file_task in scan.plan_files():
            f = file_task.file
            ref = FileRef(
                path=f.path,
                content_type=f.content_type.name,
                partition=dict(f.partition) if f.partition is not None else {},
                file_size_bytes=f.file_size_in_bytes,
                record_count=f.record_count,
                sequence_number=f.file_sequence_number,
                data_sequence_number=f.data_sequence_number,
                extra={
                    "spec_id": f.spec_id,
                    "sort_order_id": getattr(f, "sort_order_id", None),
                },
            )
            if ref.content_type == "DATA":
                data_files.append(ref)
            else:
                delete_files.append(ref)

        return SnapshotInfo(
            snapshot_id=snapshot.snapshot_id,
            parent_id=snapshot.parent_snapshot_id,
            timestamp_ms=snapshot.timestamp_ms,
            operation=snapshot.operation,
            summary=dict(snapshot.summary),
            data_files=data_files,
            delete_files=delete_files,
        )
