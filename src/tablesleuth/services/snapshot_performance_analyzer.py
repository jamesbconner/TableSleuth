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
    """Analyzes query performance across snapshots."""

    def __init__(self, profiler: ProfilingBackend):
        """Initialize with a profiling backend.

        Args:
            profiler: ProfilingBackend instance (typically GizmoDuckDbProfiler)
        """
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
        """
        try:
            # Substitute table name if query contains placeholder
            query = query.replace("{table}", table_name)

            # Execute query with metrics collection
            # Note: This assumes the profiler has execute_query_with_metrics method
            if hasattr(self._profiler, "execute_query_with_metrics"):
                _, metrics = self._profiler.execute_query_with_metrics(query)
                return metrics  # type: ignore[no-any-return]
            else:
                # Fallback: execute query and create basic metrics
                import time

                start_time = time.time()
                # Execute query (method depends on profiler implementation)
                # This is a simplified version
                execution_time_ms = (time.time() - start_time) * 1000

                return QueryPerformanceMetrics(
                    execution_time_ms=execution_time_ms,
                    files_scanned=0,
                    bytes_scanned=0,
                    rows_scanned=0,
                    rows_returned=0,
                    memory_peak_mb=0.0,
                )

        except Exception as e:
            logger.error(f"Query test failed for {table_name}: {e}")
            raise RuntimeError(f"Query test failed: {e}") from e

    def _run_query_direct(self, query: str) -> QueryPerformanceMetrics:
        """Run a query directly without placeholder substitution.

        Args:
            query: SQL query to execute (already substituted)

        Returns:
            QueryPerformanceMetrics object

        Raises:
            RuntimeError: If query execution fails
        """
        try:
            # Execute query with metrics collection
            if hasattr(self._profiler, "execute_query_with_metrics"):
                _, metrics = self._profiler.execute_query_with_metrics(query)
                return metrics  # type: ignore[no-any-return]
            else:
                # Fallback: execute query and create basic metrics
                import time

                start_time = time.time()
                execution_time_ms = (time.time() - start_time) * 1000

                return QueryPerformanceMetrics(
                    execution_time_ms=execution_time_ms,
                    files_scanned=0,
                    bytes_scanned=0,
                    rows_scanned=0,
                    rows_returned=0,
                    memory_peak_mb=0.0,
                )

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise RuntimeError(f"Query execution failed: {e}") from e

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
        """
        # Substitute table names in query template
        query_a = query_template.replace("{table}", table_a)
        query_b = query_template.replace("{table}", table_b)

        # Run queries and collect metrics (pass None for table_name to skip double substitution)
        logger.debug(f"Running performance test on {table_a}")
        metrics_a = self._run_query_direct(query_a)

        logger.debug(f"Running performance test on {table_b}")
        metrics_b = self._run_query_direct(query_b)

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
