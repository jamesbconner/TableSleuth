"""Performance profiling models for merge-on-read analysis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QueryPerformanceProfile:
    """Performance metrics for a query execution."""

    query: str
    execution_time_ms: float
    rows_scanned: int
    rows_returned: int
    delete_files_applied: int
    data_files_scanned: int


@dataclass
class MergeOnReadPerformance:
    """Performance comparison of queries with and without delete application."""

    with_deletes: QueryPerformanceProfile
    without_deletes: QueryPerformanceProfile

    @property
    def overhead_ms(self) -> float:
        """Time overhead caused by merge-on-read in milliseconds."""
        return self.with_deletes.execution_time_ms - self.without_deletes.execution_time_ms

    @property
    def overhead_percentage(self) -> float:
        """
        Percentage overhead caused by merge-on-read.

        Returns:
            Percentage overhead (0-100+). Returns float('inf') if base query
            time is zero but overhead exists (representing infinite percentage
            overhead). Returns 0.0 if both times are zero.
        """
        if self.without_deletes.execution_time_ms == 0:
            # If base time is 0 but there's overhead, return infinity
            if self.overhead_ms > 0:
                return float("inf")
            # If both are 0, return 0
            return 0.0
        return (self.overhead_ms / self.without_deletes.execution_time_ms) * 100

    @property
    def rows_deleted(self) -> int:
        """
        Number of rows filtered out by delete files.

        Returns:
            Non-negative count of deleted rows. Returns 0 if the calculation
            would be negative (which can occur due to timing differences,
            data changes between measurements, or backend inconsistencies).
        """
        deleted = self.without_deletes.rows_returned - self.with_deletes.rows_returned
        return max(0, deleted)
