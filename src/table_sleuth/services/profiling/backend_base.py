from __future__ import annotations

from collections.abc import Sequence
from typing import Dict, Optional, Protocol

from table_sleuth.models import (
    ColumnProfile,
    MergeOnReadPerformance,
    SnapshotInfo,
)


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

    def profile_query_performance(
        self,
        snapshot: SnapshotInfo,
        query: str,
        filters: Optional[str] = None,
    ) -> MergeOnReadPerformance:
        """
        Profile query performance with and without delete file application.

        Args:
            snapshot: The snapshot to profile
            query: SQL query to execute (e.g., "SELECT COUNT(*)")
            filters: Optional WHERE clause filters

        Returns:
            Performance comparison showing merge-on-read overhead

        Note:
            This is an optional method. Backends that don't support performance
            profiling can raise NotImplementedError.
        """
        ...
