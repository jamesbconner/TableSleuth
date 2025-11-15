from __future__ import annotations

from typing import Dict, Sequence, Optional

from table_sleuth.models import SnapshotInfo, ColumnProfile
from .backend_base import ProfilingBackend


class FakeProfiler(ProfilingBackend):
    """Simple fake profiler used for tests."""

    def register_snapshot_view(self, snapshot: SnapshotInfo) -> str:
        return f"fake_{snapshot.snapshot_id}"

    def profile_single_column(
        self,
        view_name: str,
        column: str,
        filters: Optional[str] = None,
    ) -> ColumnProfile:
        return ColumnProfile(
            column=column,
            row_count=100,
            non_null_count=90,
            null_count=10,
            distinct_count=5,
            min_value=None,
            max_value=None,
        )

    def profile_columns(
        self,
        view_name: str,
        columns: Sequence[str],
        filters: Optional[str] = None,
    ) -> Dict[str, ColumnProfile]:
        return {
            col: self.profile_single_column(view_name, col, filters)
            for col in columns
        }
