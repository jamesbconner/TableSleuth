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
        """Test that unreasonably large COUNT values are treated as 1."""
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

        # Unreasonably large value (>1B rows) - probably not a real row count
        results = [[5_000_000_000]]

        metrics = profiler._supplement_metrics(mock_metrics, "SELECT COUNT(*) FROM table", results)

        # Should be 1 (sanity check failed)
        assert metrics.rows_returned == 1

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
