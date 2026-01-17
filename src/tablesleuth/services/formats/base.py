from __future__ import annotations

from collections.abc import Iterable
from typing import Optional, Protocol

from tablesleuth.models import FileRef, SnapshotInfo, TableHandle


class TableFormatAdapter(Protocol):
    """Format neutral interface for table metadata access."""

    def open_table(self, identifier: str, catalog_name: str | None = None) -> TableHandle: ...

    def list_snapshots(self, table: TableHandle) -> list[SnapshotInfo]: ...

    def load_snapshot(self, table: TableHandle, snapshot_id: int | None) -> SnapshotInfo: ...

    def iter_data_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]: ...

    def iter_delete_files(self, snapshot: SnapshotInfo) -> Iterable[FileRef]: ...
