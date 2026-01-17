"""Tests for SnapshotPerformanceAnalyzer."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from tablesleuth.models.iceberg import QueryPerformanceMetrics
from tablesleuth.services.snapshot_performance_analyzer import (
    SnapshotPerformanceAnalyzer,
)


class TestSnapshotPerformanceAnalyzer:
    """Tests for SnapshotPerformanceAnalyzer."""

    def test_get_predefined_queries(self):
        """Test getting predefined query templates."""
        mock_profiler = Mock()
        analyzer = SnapshotPerformanceAnalyzer(mock_profiler)

        queries = analyzer.get_predefined_queries()

        assert isinstance(queries, dict)
        assert len(queries) > 0
        assert "full_scan" in queries
        assert "filtered_scan" in queries
        assert "aggregation" in queries
        assert "point_lookup" in queries

        # Verify queries have {table} placeholder
        for query in queries.values():
            assert "{table}" in query

    def test_run_query_test(self):
        """Test running a query test."""
        # Mock profiler
        mock_profiler = Mock()
        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )
        mock_profiler.execute_query_with_metrics.return_value = ([], mock_metrics)

        analyzer = SnapshotPerformanceAnalyzer(mock_profiler)

        # Run test
        metrics = analyzer.run_query_test("test_table", "SELECT * FROM {table}")

        assert metrics is not None
        assert metrics.execution_time_ms == 100.0
        assert metrics.files_scanned == 10

        # Verify profiler was called with substituted query
        mock_profiler.execute_query_with_metrics.assert_called_once()
        call_args = mock_profiler.execute_query_with_metrics.call_args
        assert "test_table" in call_args[0][0]
        assert "{table}" not in call_args[0][0]

    def test_compare_query_performance(self):
        """Test comparing query performance between two tables."""
        # Mock profiler
        mock_profiler = Mock()

        metrics_a = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )

        metrics_b = QueryPerformanceMetrics(
            execution_time_ms=150.0,
            files_scanned=15,
            bytes_scanned=1500000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=60.0,
        )

        # Return different metrics for each call
        mock_profiler.execute_query_with_metrics.side_effect = [
            ([], metrics_a),
            ([], metrics_b),
        ]

        analyzer = SnapshotPerformanceAnalyzer(mock_profiler)

        # Compare
        comparison = analyzer.compare_query_performance(
            "table_a", "table_b", "SELECT * FROM {table}"
        )

        assert comparison is not None
        assert comparison.table_a_name == "table_a"
        assert comparison.table_b_name == "table_b"
        assert comparison.metrics_a == metrics_a
        assert comparison.metrics_b == metrics_b
        assert comparison.execution_time_delta_pct == 50.0

        # Verify profiler was called twice
        assert mock_profiler.execute_query_with_metrics.call_count == 2

    def test_query_template_substitution(self):
        """Test that query templates are properly substituted."""
        mock_profiler = Mock()
        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=10,
            bytes_scanned=1000000,
            rows_scanned=1000,
            rows_returned=500,
            memory_peak_mb=50.0,
        )
        mock_profiler.execute_query_with_metrics.return_value = ([], mock_metrics)

        analyzer = SnapshotPerformanceAnalyzer(mock_profiler)

        # Test with template containing {table}
        analyzer.run_query_test("my_table", "SELECT COUNT(*) FROM {table}")

        # Verify the query was substituted
        call_args = mock_profiler.execute_query_with_metrics.call_args
        executed_query = call_args[0][0]
        assert "my_table" in executed_query
        assert "{table}" not in executed_query
        assert "SELECT COUNT(*) FROM my_table" == executed_query

    # Integration tests requiring real profiler

    @pytest.mark.integration
    def test_run_query_test_integration(self, profiler, registered_snapshot_table):
        """Test running a query test with real profiler.

        Args:
            profiler: Real profiling backend
            registered_snapshot_table: Name of registered snapshot table
        """
        analyzer = SnapshotPerformanceAnalyzer(profiler)

        metrics = analyzer.run_query_test(registered_snapshot_table, "SELECT COUNT(*) FROM {table}")

        assert metrics is not None
        assert metrics.execution_time_ms > 0
        assert metrics.files_scanned >= 0
        assert metrics.rows_scanned >= 0

    @pytest.mark.integration
    def test_compare_query_performance_integration(self, profiler, registered_snapshot_tables):
        """Test comparing query performance with real profiler.

        Args:
            profiler: Real profiling backend
            registered_snapshot_tables: Tuple of (table_a, table_b) names
        """
        table_a, table_b = registered_snapshot_tables
        analyzer = SnapshotPerformanceAnalyzer(profiler)

        comparison = analyzer.compare_query_performance(
            table_a, table_b, "SELECT COUNT(*) FROM {table}"
        )

        assert comparison is not None
        assert comparison.metrics_a.execution_time_ms > 0
        assert comparison.metrics_b.execution_time_ms > 0
        assert comparison.analysis is not None


# Fixtures for integration tests
@pytest.fixture
def profiler():
    """Provide a real profiling backend for integration tests."""
    from tablesleuth.config import load_config
    from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler

    config = load_config()
    try:
        profiler = GizmoDuckDbProfiler(
            uri=config.gizmosql.uri,
            username=config.gizmosql.username,
            password=config.gizmosql.password,
            tls_skip_verify=config.gizmosql.tls_skip_verify,
        )
        return profiler
    except Exception:
        pytest.skip("GizmoSQL not available")


@pytest.fixture
def registered_snapshot_table(profiler):
    """Provide a registered snapshot table for testing."""
    # This would require setting up a test catalog and registering a snapshot
    # Skip if not available
    pytest.skip("Requires test catalog setup")


@pytest.fixture
def registered_snapshot_tables(profiler):
    """Provide two registered snapshot tables for comparison testing."""
    # This would require setting up a test catalog and registering two snapshots
    # Skip if not available
    pytest.skip("Requires test catalog setup")
