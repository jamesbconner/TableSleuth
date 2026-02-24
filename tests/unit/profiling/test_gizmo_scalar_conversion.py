"""Tests for scalar query result conversion in _supplement_metrics."""

from decimal import Decimal

import pytest

from tablesleuth.models.iceberg import QueryPerformanceMetrics
from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler


class TestScalarConversion:
    """Tests for rows_returned inference from scalar query results."""

    def test_supplement_metrics_with_int_result(self) -> None:
        """Test that integer COUNT results are handled correctly."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        # Mock metrics with zero rows_returned
        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Single-cell result with int from COUNT query
        results = [[42]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT COUNT(*) FROM table", results)

        assert metrics.rows_returned == 42

    def test_supplement_metrics_with_sum_aggregate(self) -> None:
        """Test that SUM aggregates are not misinterpreted as row counts."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Single-cell result with large value from SUM query
        results = [[5000000]]

        metrics = profiler._supplement_metrics(
            mock_metrics, "SELECT SUM(price) FROM table", results
        )

        # Should be 1 (one result row), not 5000000
        assert metrics.rows_returned == 1

    def test_supplement_metrics_with_avg_aggregate(self) -> None:
        """Test that AVG aggregates are not misinterpreted as row counts."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Single-cell result from AVG query
        results = [[42.5]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT AVG(age) FROM table", results)

        # Should be 1 (one result row)
        assert metrics.rows_returned == 1

    def test_supplement_metrics_with_max_aggregate(self) -> None:
        """Test that MAX aggregates are not misinterpreted as row counts."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Single-cell result from MAX query
        results = [[999999]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT MAX(id) FROM table", results)

        # Should be 1 (one result row)
        assert metrics.rows_returned == 1

    def test_supplement_metrics_with_unreasonably_large_count(self) -> None:
        """Test that large COUNT values (>1B) are accepted for data warehouse tables."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Large value (5B rows) - valid for data warehouse tables (Iceberg, Delta Lake)
        results = [[5_000_000_000]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT COUNT(*) FROM table", results)

        # Should accept the large count value
        assert metrics.rows_returned == 5_000_000_000

    def test_supplement_metrics_with_float_result(self) -> None:
        """Test that float COUNT results are converted to int."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Single-cell result with float
        results = [[123.0]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT COUNT(*) FROM table", results)

        assert metrics.rows_returned == 123

    def test_supplement_metrics_with_decimal_result(self) -> None:
        """Test that Decimal COUNT results are converted to int."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Single-cell result with Decimal (common from some SQL engines)
        results = [[Decimal("999")]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT COUNT(*) FROM table", results)

        assert metrics.rows_returned == 999

    def test_supplement_metrics_with_string_numeric_result(self) -> None:
        """Test that string numeric results are converted to int."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Single-cell result with string number
        results = [["456"]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT COUNT(*) FROM table", results)

        assert metrics.rows_returned == 456

    def test_supplement_metrics_with_non_numeric_result(self) -> None:
        """Test that non-numeric scalar results default to 1."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Single-cell result with non-numeric value
        results = [["some_string"]]

        metrics = profiler._supplement_metrics(
            mock_metrics, "SELECT name FROM table LIMIT 1", results
        )

        # Should default to 1 for non-numeric scalar
        assert metrics.rows_returned == 1

    def test_supplement_metrics_with_multiple_rows(self) -> None:
        """Test that multi-row results use row count."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Multiple rows
        results = [[1, "a"], [2, "b"], [3, "c"]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT id, name FROM table", results)

        assert metrics.rows_returned == 3

    def test_supplement_metrics_with_multiple_columns(self) -> None:
        """Test that single row with multiple columns uses row count."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Single row, multiple columns
        results = [[1, "a", 100.5]]

        metrics = profiler._supplement_metrics(
            mock_metrics, "SELECT id, name, value FROM table LIMIT 1", results
        )

        # Should use row count (1) not try to convert first cell
        assert metrics.rows_returned == 1

    def test_supplement_metrics_with_empty_results(self) -> None:
        """Test that empty results don't crash."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Empty results
        results = []

        metrics = profiler._supplement_metrics(
            mock_metrics, "SELECT * FROM table WHERE 1=0", results
        )

        # Should remain 0
        assert metrics.rows_returned == 0

    def test_supplement_metrics_preserves_existing_rows_returned(self) -> None:
        """Test that existing rows_returned is not overwritten."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=50,  # Already set
            memory_peak_mb=0,
        )

        # Results that would suggest different value
        results = [[100]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT COUNT(*) FROM table", results)

        # Should preserve existing value
        assert metrics.rows_returned == 50

    def test_supplement_metrics_count_over_one_billion(self) -> None:
        """Test that COUNT results over 1 billion are accepted for data warehouse tables."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # COUNT result of 5 billion rows (common for large Iceberg/Delta tables)
        results = [[5_000_000_000]]

        metrics = profiler._supplement_metrics(
            mock_metrics, "SELECT COUNT(*) FROM large_table", results
        )

        assert metrics.rows_returned == 5_000_000_000

    def test_supplement_metrics_count_exactly_one_billion(self) -> None:
        """Test that COUNT result of exactly 1 billion is accepted."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        results = [[1_000_000_000]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT COUNT(*) FROM table", results)

        assert metrics.rows_returned == 1_000_000_000

    def test_supplement_metrics_count_ten_billion(self) -> None:
        """Test that COUNT result of 10 billion is accepted."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        results = [[10_000_000_000]]

        metrics = profiler._supplement_metrics(
            mock_metrics, "SELECT COUNT(*) FROM huge_table", results
        )

        assert metrics.rows_returned == 10_000_000_000

    def test_supplement_metrics_count_negative_rejected(self) -> None:
        """Test that negative COUNT results are rejected (invalid)."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=0,
            bytes_scanned=0,
            rows_scanned=0,
            rows_returned=0,
            memory_peak_mb=0,
        )

        # Negative count is invalid
        results = [[-100]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT COUNT(*) FROM table", results)

        # Should default to 1 (single result row) for invalid counts
        assert metrics.rows_returned == 1

    def test_supplement_metrics_scan_efficiency_with_large_count(self) -> None:
        """Test that scan_efficiency is calculated correctly with large COUNT results."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )

        # Simulate a full table scan with 5B rows
        mock_metrics = QueryPerformanceMetrics(
            execution_time_ms=100,
            files_scanned=1000,
            bytes_scanned=500_000_000_000,  # 500 GB
            rows_scanned=5_000_000_000,  # 5B rows scanned
            rows_returned=0,  # Will be filled from results
            memory_peak_mb=1024,
        )

        results = [[5_000_000_000]]  # COUNT(*) returns 5B

        metrics = profiler._supplement_metrics(
            mock_metrics, "SELECT COUNT(*) FROM large_table", results
        )

        assert metrics.rows_returned == 5_000_000_000
        assert metrics.rows_scanned == 5_000_000_000

        # Scan efficiency should be 100% (all scanned rows returned)
        # scan_efficiency = rows_returned / rows_scanned = 5B / 5B = 1.0 = 100%
        # This is calculated elsewhere, but the metrics should support it
        if metrics.rows_scanned > 0:
            scan_efficiency = metrics.rows_returned / metrics.rows_scanned
            assert scan_efficiency == 1.0
