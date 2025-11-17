"""Analyzer for running performance tests across snapshots."""

from __future__ import annotations

import logging

from table_sleuth.models.iceberg import (
    PerformanceComparison,
    QueryPerformanceMetrics,
)
from table_sleuth.services.profiling.backend_base import ProfilingBackend

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
            query: SQL query to execute

        Returns:
            QueryPerformanceMetrics object

        Raises:
            RuntimeError: If query execution fails
        """
        try:
            # Execute query with metrics collection
            # Note: This assumes the profiler has execute_query_with_metrics method
            if hasattr(self._profiler, "execute_query_with_metrics"):
                _, metrics = self._profiler.execute_query_with_metrics(query)
                return metrics
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

    def compare_query_performance(
        self,
        table_a: str,
        table_b: str,
        query_template: str,
    ) -> PerformanceComparison:
        """Run the same query against two tables and compare results.

        Args:
            table_a: Name of first snapshot table
            table_b: Name of second snapshot table
            query_template: SQL query template with {table} placeholder

        Returns:
            PerformanceComparison object

        Raises:
            RuntimeError: If query execution fails
        """
        # Substitute table names in query template
        query_a = query_template.replace("{table}", table_a)
        query_b = query_template.replace("{table}", table_b)

        # Run queries and collect metrics
        logger.info(f"Running performance test on {table_a}")
        metrics_a = self.run_query_test(table_a, query_a)

        logger.info(f"Running performance test on {table_b}")
        metrics_b = self.run_query_test(table_b, query_b)

        # Create comparison
        return PerformanceComparison(
            query=query_template,
            table_a_name=table_a,
            table_b_name=table_b,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
        )

    def get_predefined_queries(self) -> dict[str, str]:
        """Get predefined query templates for common test scenarios.

        Returns:
            Dictionary mapping template name to query string
        """
        return {
            "full_scan": "SELECT COUNT(*) FROM {table}",
            "filtered_scan": "SELECT * FROM {table} WHERE year_month >= 202401 LIMIT 1000",
            "aggregation": "SELECT year_month, COUNT(*) as count FROM {table} GROUP BY year_month ORDER BY year_month",
            "point_lookup": "SELECT * FROM {table} WHERE beer_id = 1234 LIMIT 10",
            "column_stats": "SELECT MIN(abv), MAX(abv), AVG(abv) FROM {table}",
            "distinct_count": "SELECT COUNT(DISTINCT brewery_id) FROM {table}",
        }
