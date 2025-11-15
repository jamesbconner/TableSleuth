from __future__ import annotations

from collections.abc import Sequence
from typing import Dict, Optional, Protocol

from table_sleuth.models import ColumnProfile, SnapshotInfo


class ProfilingBackend(Protocol):
    def register_snapshot_view(self, snapshot: SnapshotInfo) -> str:
        """Create a backend-specific view for this snapshot, returns the view name."""

    def profile_single_column(
        self,
        view_name: str,
        column: str,
        filters: Optional[str] = None,
    ) -> ColumnProfile: ...

    def profile_columns(
        self,
        view_name: str,
        columns: Sequence[str],
        filters: Optional[str] = None,
    ) -> dict[str, ColumnProfile]: ...
