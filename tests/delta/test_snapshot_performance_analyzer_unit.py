"""Unit tests for SnapshotPerformanceAnalyzer."""

from unittest.mock import Mock

import pytest

from tablesleuth.models.iceberg import QueryPerformanceMetrics
from tablesleuth.services.snapshot_performance_analyzer import (
    SnapshotPerformanceAnalyzer,
)


class TestSnapshotPerformanceAnalyzer:
    """Tests for SnapshotPerformanceAnalyzer class."""

    @pytest.fixture
    def mock_profiler(self):
        """Create a mock profiling backend."""
        profiler = Mock()
        profiler.execute_query_with_metrics = Mock()
        return profiler

    @pytest.fixture
    def analyzer(self, mock_profiler):
        """Create analyzer with mock profiler."""
        return SnapshotPerformanceAnalyzer(mock_profiler)

    def test_init(self, mock_profiler):
        """Test analyzer initialization."""
        analyzer = SnapshotPerformanceAnalyzer(mock_profiler)
        assert analyzer._profiler == mock_profiler

    def test_init_validates_profiler_interface(self):
        """Test that initialization validates profiler has required methods."""
        # Create profiler without execute_query_with_metrics
        invalid_profiler = Mock(spec=[])

        with pytest.raises(ValueError, match="must implement execute_query_with_metrics"):
            SnapshotPerformanceAnalyzer(invalid_profiler)

    def test_init_validates_method_is_callable(self):
        """Test that initialization validates method is callable."""
        # Create profiler with non-callable attribute
        invalid_profiler = Mock()
        invalid_profiler.execute_query_with_metrics = "not_callable"

        with pytest.raises(ValueError, match="must be a callable method"):
            SnapshotPerformanceAnalyzer(invalid_profiler)

    def test_run_query_test_with_placeholder(self, analyzer, mock_profiler):
        """Test running query with table placeholder."""
        # Setup mock
        expected_metrics = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=5,
            bytes_scanned=1024,
            rows_scanned=1000,
            rows_returned=100,
            memory_peak_mb=10.5,
        )
        mock_profiler.execute_query_with_metrics.return_value = (None, expected_metrics)

        # Execute
        result = analyzer.run_query_test(
            table_name="test_table",
            query="SELECT * FROM {table} LIMIT 10",
        )

        # Verify
        assert result == expected_metrics
        mock_profiler.execute_query_with_metrics.assert_called_once_with(
            "SELECT * FROM test_table LIMIT 10"
        )

    def test_run_query_test_without_placeholder(self, analyzer, mock_profiler):
        """Test running query without placeholder."""
        expected_metrics = QueryPerformanceMetrics(
            execution_time_ms=50.0,
            files_scanned=2,
            bytes_scanned=512,
            rows_scanned=500,
            rows_returned=50,
            memory_peak_mb=5.0,
        )
        mock_profiler.execute_query_with_metrics.return_value = (None, expected_metrics)

        result = analyzer.run_query_test(
            table_name="test_table",
            query="SELECT COUNT(*) FROM test_table",
        )

        assert result == expected_metrics

    def test_run_query_test_error_handling(self, analyzer, mock_profiler):
        """Test error handling when query fails."""
        mock_profiler.execute_query_with_metrics.side_effect = Exception("Query failed")

        with pytest.raises(RuntimeError, match="Query test failed"):
            analyzer.run_query_test("test_table", "SELECT * FROM {table}")

    def test_compare_query_performance(self, analyzer, mock_profiler):
        """Test comparing performance between two tables."""
        metrics_a = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=5,
            bytes_scanned=1024,
            rows_scanned=1000,
            rows_returned=100,
            memory_peak_mb=10.0,
        )
        metrics_b = QueryPerformanceMetrics(
            execution_time_ms=150.0,
            files_scanned=8,
            bytes_scanned=2048,
            rows_scanned=1500,
            rows_returned=150,
            memory_peak_mb=15.0,
        )

        # Mock returns different metrics for each call
        mock_profiler.execute_query_with_metrics.side_effect = [
            (None, metrics_a),
            (None, metrics_b),
        ]

        result = analyzer.compare_query_performance(
            table_a="snapshot_1",
            table_b="snapshot_2",
            query_template="SELECT * FROM {table} LIMIT 100",
        )

        # Verify comparison
        assert result.table_a_name == "snapshot_1"
        assert result.table_b_name == "snapshot_2"
        assert result.metrics_a == metrics_a
        assert result.metrics_b == metrics_b
        assert result.query == "SELECT * FROM {table} LIMIT 100"

        # Verify both queries were executed
        assert mock_profiler.execute_query_with_metrics.call_count == 2

    def test_compare_query_performance_error_on_first_query(self, analyzer, mock_profiler):
        """Test error handling when first query fails."""
        mock_profiler.execute_query_with_metrics.side_effect = Exception("Query failed")

        with pytest.raises(RuntimeError, match="Query test failed"):
            analyzer.compare_query_performance("table_a", "table_b", "SELECT * FROM {table}")

    def test_compare_query_performance_error_on_second_query(self, analyzer, mock_profiler):
        """Test error handling when second query fails."""
        metrics_a = QueryPerformanceMetrics(
            execution_time_ms=100.0,
            files_scanned=5,
            bytes_scanned=1024,
            rows_scanned=1000,
            rows_returned=100,
            memory_peak_mb=10.0,
        )

        mock_profiler.execute_query_with_metrics.side_effect = [
            (None, metrics_a),
            Exception("Second query failed"),
        ]

        with pytest.raises(RuntimeError, match="Query test failed"):
            analyzer.compare_query_performance("table_a", "table_b", "SELECT * FROM {table}")

    def test_get_predefined_queries(self, analyzer):
        """Test getting predefined query templates."""
        queries = analyzer.get_predefined_queries()

        # Verify expected queries exist
        assert "full_scan" in queries
        assert "sample_rows" in queries
        assert "table_stats" in queries
        assert "filtered_scan" in queries
        assert "aggregation" in queries
        assert "point_lookup" in queries
        assert "column_stats" in queries
        assert "distinct_count" in queries

        # Verify queries contain placeholders
        assert "{table}" in queries["full_scan"]
        assert "{table}" in queries["sample_rows"]
        assert "{column}" in queries["filtered_scan"]
        assert "{numeric_column}" in queries["column_stats"]

    def test_predefined_query_full_scan(self, analyzer):
        """Test full scan query template."""
        queries = analyzer.get_predefined_queries()
        query = queries["full_scan"]

        assert query == "SELECT COUNT(*) FROM {table}"

    def test_predefined_query_sample_rows(self, analyzer):
        """Test sample rows query template."""
        queries = analyzer.get_predefined_queries()
        query = queries["sample_rows"]

        assert "SELECT * FROM {table}" in query
        assert "LIMIT" in query
