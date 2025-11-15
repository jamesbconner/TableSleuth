from __future__ import annotations
from typing import Iterable, Protocol, Optional

from table_sleuth.models import TableHandle, SnapshotInfo, FileRef


class TableFormatAdapter(Protocol):
    """Format neutral interface for table metadata access."""

    def open_table(self, identifier: str, catalog_name: Optional[str] = None) -> TableHandle:
        ...

    def list_snapshots(self, table: TableHandle) -> list[SnapshotInfo]:
        ...

    def load_snapshot(self, table: TableHandle, snapshot_id: Optional[int]) -> SnapshotInfo:
        ...

    def iter_data_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]:
        ...

    def iter_delete_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]:
        ...
