"""Analyzer for running performance tests across snapshots."""

from __future__ import annotations

import logging

from tablesleuth.models.iceberg import (
    IcebergSnapshotInfo,
    PerformanceComparison,
    QueryPerformanceMetrics,
)
from tablesleuth.services.profiling.backend_base import ProfilingBackend

logger = logging.getLogger(__name__)


class SnapshotPerformanceAnalyzer:
    """Analyzes query performance across snapshots.

    This class requires a profiling backend that implements the
    execute_query_with_metrics method for collecting performance metrics.
    """

    def __init__(self, profiler: ProfilingBackend):
        """Initialize with a profiling backend.

        Args:
            profiler: ProfilingBackend instance that implements execute_query_with_metrics

        Raises:
            ValueError: If profiler doesn't support required methods

        Examples:
            >>> from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler
            >>> profiler = GizmoDuckDbProfiler(uri="grpc://localhost:31337")
            >>> analyzer = SnapshotPerformanceAnalyzer(profiler)
        """
        # Validate that profiler implements required interface
        if not hasattr(profiler, "execute_query_with_metrics"):
            raise ValueError(
                f"Profiler {type(profiler).__name__} must implement "
                "execute_query_with_metrics method. "
                "Please use a profiler that supports performance metrics collection."
            )

        # Verify the method is callable
        if not callable(getattr(profiler, "execute_query_with_metrics", None)):
            raise ValueError(
                f"Profiler {type(profiler).__name__}.execute_query_with_metrics "
                "must be a callable method."
            )

        self._profiler = profiler

    def run_query_test(
        self,
        table_name: str,
        query: str,
    ) -> QueryPerformanceMetrics:
        """Run a query against a snapshot table and collect metrics.

        Args:
            table_name: Name of the snapshot table to query
            query: SQL query to execute (can contain {table} placeholder)

        Returns:
            QueryPerformanceMetrics object

        Raises:
            RuntimeError: If query execution fails

        Examples:
            >>> metrics = analyzer.run_query_test(
            ...     "my_snapshot_table",
            ...     "SELECT COUNT(*) FROM {table}"
            ... )
            >>> print(f"Execution time: {metrics.execution_time_ms}ms")
        """
        try:
            # Substitute table name if query contains placeholder
            query = query.replace("{table}", table_name)

            # Execute query with metrics collection
            _, metrics = self._profiler.execute_query_with_metrics(query)
            return metrics  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"Query test failed for {table_name}: {e}")
            raise RuntimeError(f"Query test failed: {e}") from e

    def compare_query_performance(
        self,
        table_a: str,
        table_b: str,
        query_template: str,
        snapshot_a_info: IcebergSnapshotInfo | None = None,
        snapshot_b_info: IcebergSnapshotInfo | None = None,
    ) -> PerformanceComparison:
        """Run the same query against two tables and compare results.

        Args:
            table_a: Name of first snapshot table
            table_b: Name of second snapshot table
            query_template: SQL query template with {table} placeholder
            snapshot_a_info: Full snapshot info for snapshot A (optional, for detailed analysis)
            snapshot_b_info: Full snapshot info for snapshot B (optional, for detailed analysis)

        Returns:
            PerformanceComparison object

        Raises:
            RuntimeError: If query execution fails

        Examples:
            >>> comparison = analyzer.compare_query_performance(
            ...     "snapshot_v1",
            ...     "snapshot_v2",
            ...     "SELECT COUNT(*) FROM {table}",
            ...     snapshot_a_info=info_v1,
            ...     snapshot_b_info=info_v2
            ... )
            >>> print(comparison.analysis)
        """
        # Run queries and collect metrics
        logger.debug(f"Running performance test on {table_a}")
        metrics_a = self.run_query_test(table_a, query_template)

        logger.debug(f"Running performance test on {table_b}")
        metrics_b = self.run_query_test(table_b, query_template)

        # Create comparison with full snapshot info
        return PerformanceComparison(
            query=query_template,
            table_a_name=table_a,
            table_b_name=table_b,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
            snapshot_a_info=snapshot_a_info,
            snapshot_b_info=snapshot_b_info,
        )

    def get_predefined_queries(self) -> dict[str, str]:
        """Get predefined query templates for common test scenarios.

        Note: Templates use placeholders that users can customize:
        - {table}: Table name (automatically replaced)
        - {column}: Column name to filter/aggregate on
        - {value}: Value to filter by
        - {numeric_column}: Numeric column for statistics
        - {id_column}: ID column for point lookups

        Returns:
            Dictionary mapping template name to query string

        Examples:
            >>> queries = analyzer.get_predefined_queries()
            >>> full_scan_query = queries["full_scan"]
            >>> print(full_scan_query)
            SELECT COUNT(*) FROM {table}
        """
        return {
            "full_scan": "SELECT COUNT(*) FROM {table}",
            "sample_rows": "SELECT * FROM {table} LIMIT 1000",
            "table_stats": "SELECT COUNT(*) as row_count FROM {table}",
            "filtered_scan": "SELECT * FROM {table} WHERE {column} >= {value} LIMIT 1000",
            "aggregation": "SELECT {column}, COUNT(*) as count FROM {table} GROUP BY {column} ORDER BY {column}",
            "point_lookup": "SELECT * FROM {table} WHERE {id_column} = {value} LIMIT 10",
            "column_stats": "SELECT MIN({numeric_column}), MAX({numeric_column}), AVG({numeric_column}) FROM {table}",
            "distinct_count": "SELECT COUNT(DISTINCT {column}) FROM {table}",
        }
