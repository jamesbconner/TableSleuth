from __future__ import annotations

from typing import Dict, Protocol, Sequence, Optional

from table_sleuth.models import SnapshotInfo, ColumnProfile


class ProfilingBackend(Protocol):
    def register_snapshot_view(self, snapshot: SnapshotInfo) -> str:
        """Create a backend-specific view for this snapshot, returns the view name."""

    def profile_single_column(
        self,
        view_name: str,
        column: str,
        filters: Optional[str] = None,
    ) -> ColumnProfile:
        ...

    def profile_columns(
        self,
        view_name: str,
        columns: Sequence[str],
        filters: Optional[str] = None,
    ) -> Dict[str, ColumnProfile]:
        ...
