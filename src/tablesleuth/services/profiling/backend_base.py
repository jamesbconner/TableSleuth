from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Dict, Optional

from tablesleuth.models import (
    ColumnProfile,
    MergeOnReadPerformance,
    SnapshotInfo,
)


class ProfilingBackend(ABC):
    """
    Abstract base class for profiling backends.

    Backends must implement the core profiling methods. Performance profiling
    is optional and will raise NotImplementedError by default.
    """

    @abstractmethod
    def register_snapshot_view(self, snapshot: SnapshotInfo) -> str:
        """Create a backend-specific view for this snapshot, returns the view name."""
        ...

    @abstractmethod
    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str:
        """Create a backend-specific view for Parquet files.

        Args:
            file_paths: List of Parquet file paths
            view_name: Optional view name (auto-generated if None)

        Returns:
            View name that can be used in subsequent queries
        """
        ...

    @abstractmethod
    def profile_single_column(
        self,
        view_name: str,
        column: str,
        filters: str | None = None,
    ) -> ColumnProfile:
        """Profile a single column in the view."""
        ...

    @abstractmethod
    def profile_columns(
        self,
        view_name: str,
        columns: Sequence[str],
        filters: str | None = None,
    ) -> dict[str, ColumnProfile]:
        """Profile multiple columns in the view."""
        ...

    def profile_query_performance(
        self,
        snapshot: SnapshotInfo,
        query: str,
        filters: str | None = None,
    ) -> MergeOnReadPerformance:
        """
        Profile query performance with and without delete file application.

        This is an optional method. The default implementation raises
        NotImplementedError. Backends that support performance profiling
        should override this method.

        Args:
            snapshot: The snapshot to profile
            query: SQL query to execute (e.g., "SELECT COUNT(*)")
            filters: Optional WHERE clause filters

        Returns:
            Performance comparison showing merge-on-read overhead

        Raises:
            NotImplementedError: If the backend doesn't support performance profiling
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support performance profiling. "
            "Override profile_query_performance() to add support."
        )

    def clear_views(self) -> None:
        """
        Clear all registered views and their associated state.

        This is an optional method. The default implementation does nothing.
        Backends that maintain internal state should override this method.
        """
        return  # Default implementation - backends override if they maintain state
