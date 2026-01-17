from __future__ import annotations

from collections.abc import Sequence
from typing import Dict, Optional

from tablesleuth.models import ColumnProfile, SnapshotInfo

from .backend_base import ProfilingBackend


class FakeProfiler(ProfilingBackend):
    """Simple fake profiler used for tests."""

    def register_snapshot_view(self, snapshot: SnapshotInfo) -> str:
        return f"fake_{snapshot.snapshot_id}"

    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str:
        """Register file view for testing."""
        if view_name:
            return view_name
        return f"fake_view_{len(file_paths)}"

    def profile_single_column(
        self,
        view_name: str,
        column: str,
        filters: str | None = None,
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
        filters: str | None = None,
    ) -> dict[str, ColumnProfile]:
        return {col: self.profile_single_column(view_name, col, filters) for col in columns}
