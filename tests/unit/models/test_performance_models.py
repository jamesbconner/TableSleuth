"""Tests for performance profiling models."""

from tablesleuth.models import MergeOnReadPerformance, QueryPerformanceProfile


class TestQueryPerformanceProfile:
    """Test suite for QueryPerformanceProfile model."""

    def test_create_profile(self):
        """Test creating a query performance profile."""
        profile = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM table",
            execution_time_ms=150.5,
            rows_scanned=1000,
            rows_returned=950,
            delete_files_applied=3,
            data_files_scanned=10,
        )

        assert profile.query == "SELECT COUNT(*) FROM table"
        assert profile.execution_time_ms == 150.5
        assert profile.rows_scanned == 1000
        assert profile.rows_returned == 950
        assert profile.delete_files_applied == 3
        assert profile.data_files_scanned == 10


class TestMergeOnReadPerformance:
    """Test suite for MergeOnReadPerformance model."""

    def test_overhead_calculation(self):
        """Test overhead calculation between queries with and without deletes."""
        without_deletes = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM table",
            execution_time_ms=100.0,
            rows_scanned=1000,
            rows_returned=1000,
            delete_files_applied=0,
            data_files_scanned=10,
        )

        with_deletes = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM table",
            execution_time_ms=150.0,
            rows_scanned=1000,
            rows_returned=950,
            delete_files_applied=3,
            data_files_scanned=10,
        )

        performance = MergeOnReadPerformance(
            with_deletes=with_deletes,
            without_deletes=without_deletes,
        )

        assert performance.overhead_ms == 50.0
        assert performance.overhead_percentage == 50.0
        assert performance.rows_deleted == 50

    def test_zero_overhead(self):
        """Test case where there's no performance overhead."""
        without_deletes = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM table",
            execution_time_ms=100.0,
            rows_scanned=1000,
            rows_returned=1000,
            delete_files_applied=0,
            data_files_scanned=10,
        )

        with_deletes = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM table",
            execution_time_ms=100.0,
            rows_scanned=1000,
            rows_returned=1000,
            delete_files_applied=0,
            data_files_scanned=10,
        )

        performance = MergeOnReadPerformance(
            with_deletes=with_deletes,
            without_deletes=without_deletes,
        )

        assert performance.overhead_ms == 0.0
        assert performance.overhead_percentage == 0.0
        assert performance.rows_deleted == 0

    def test_high_overhead(self):
        """Test case with significant merge-on-read overhead."""
        without_deletes = QueryPerformanceProfile(
            query="SELECT * FROM table WHERE date > '2024-01-01'",
            execution_time_ms=50.0,
            rows_scanned=10000,
            rows_returned=10000,
            delete_files_applied=0,
            data_files_scanned=100,
        )

        with_deletes = QueryPerformanceProfile(
            query="SELECT * FROM table WHERE date > '2024-01-01'",
            execution_time_ms=250.0,
            rows_scanned=10000,
            rows_returned=7500,
            delete_files_applied=50,
            data_files_scanned=100,
        )

        performance = MergeOnReadPerformance(
            with_deletes=with_deletes,
            without_deletes=without_deletes,
        )

        assert performance.overhead_ms == 200.0
        assert performance.overhead_percentage == 400.0
        assert performance.rows_deleted == 2500

    def test_zero_base_time_with_overhead(self):
        """Test edge case where base query time is zero but overhead exists."""
        without_deletes = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM empty_table",
            execution_time_ms=0.0,
            rows_scanned=0,
            rows_returned=0,
            delete_files_applied=0,
            data_files_scanned=0,
        )

        with_deletes = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM empty_table",
            execution_time_ms=10.0,
            rows_scanned=0,
            rows_returned=0,
            delete_files_applied=0,
            data_files_scanned=0,
        )

        performance = MergeOnReadPerformance(
            with_deletes=with_deletes,
            without_deletes=without_deletes,
        )

        assert performance.overhead_ms == 10.0
        assert performance.overhead_percentage == float("inf")  # Infinite overhead
        assert performance.rows_deleted == 0

    def test_both_times_zero(self):
        """Test edge case where both query times are zero."""
        without_deletes = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM empty_table",
            execution_time_ms=0.0,
            rows_scanned=0,
            rows_returned=0,
            delete_files_applied=0,
            data_files_scanned=0,
        )

        with_deletes = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM empty_table",
            execution_time_ms=0.0,
            rows_scanned=0,
            rows_returned=0,
            delete_files_applied=0,
            data_files_scanned=0,
        )

        performance = MergeOnReadPerformance(
            with_deletes=with_deletes,
            without_deletes=without_deletes,
        )

        assert performance.overhead_ms == 0.0
        assert performance.overhead_percentage == 0.0  # No overhead
        assert performance.rows_deleted == 0

    def test_negative_rows_deleted_edge_case(self):
        """Test edge case where with_deletes returns more rows than without_deletes.

        This shouldn't happen in normal scenarios but could occur due to:
        - Timing differences (data changed between measurements)
        - Backend inconsistencies
        - Measurement errors

        The property should return 0 instead of a negative value.
        """
        without_deletes = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM table",
            execution_time_ms=100.0,
            rows_scanned=1000,
            rows_returned=900,  # Fewer rows
            delete_files_applied=0,
            data_files_scanned=10,
        )

        with_deletes = QueryPerformanceProfile(
            query="SELECT COUNT(*) FROM table",
            execution_time_ms=150.0,
            rows_scanned=1000,
            rows_returned=950,  # More rows (shouldn't happen but could)
            delete_files_applied=3,
            data_files_scanned=10,
        )

        performance = MergeOnReadPerformance(
            with_deletes=with_deletes,
            without_deletes=without_deletes,
        )

        # Should return 0 instead of -50
        assert performance.rows_deleted == 0
        assert performance.rows_deleted >= 0  # Always non-negative
