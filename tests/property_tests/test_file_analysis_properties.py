"""Property-based tests for Delta Lake file analysis.

These tests validate universal properties that should hold across all inputs
using hypothesis for comprehensive input coverage.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tablesleuth.models import FileRef, SnapshotInfo
from tablesleuth.services.delta_forensics import DeltaForensics

# Define size constants
MB = 1024 * 1024
SIZE_1MB = 1 * MB
SIZE_10MB = 10 * MB
SIZE_100MB = 100 * MB


# Custom strategies for generating test data
@st.composite
def file_size_strategy(draw):
    """Generate realistic file sizes (1KB to 1GB)."""
    return draw(st.integers(min_value=1024, max_value=1024 * MB))


@st.composite
def snapshot_with_files_strategy(draw):
    """Generate a SnapshotInfo with random data files."""
    file_count = draw(st.integers(min_value=0, max_value=100))

    data_files = []
    for i in range(file_count):
        file_size = draw(file_size_strategy())
        data_files.append(
            FileRef(
                path=f"file{i}.parquet",
                file_size_bytes=file_size,
            )
        )

    return SnapshotInfo(
        snapshot_id=draw(st.integers(min_value=0, max_value=1000)),
        parent_id=draw(st.integers(min_value=0, max_value=999) | st.none()),
        timestamp_ms=draw(st.integers(min_value=1000000000000, max_value=2000000000000)),
        operation=draw(st.sampled_from(["WRITE", "MERGE", "UPDATE", "DELETE", "OPTIMIZE"])),
        summary={},
        data_files=data_files,
    )


class TestFileAnalysisProperties:
    """Property-based tests for file size analysis."""

    @settings(max_examples=100)
    @given(snapshot=snapshot_with_files_strategy())
    def test_property_7_file_size_distribution_calculation(self, snapshot: SnapshotInfo):
        """Test file size distribution calculation.

        For any version with data files, calculating file size distribution should
        produce a histogram with correct counts for each size bucket.
        """
        result = DeltaForensics.analyze_file_sizes(snapshot)

        # Verify histogram structure
        assert "histogram" in result
        histogram = result["histogram"]
        assert set(histogram.keys()) == {"< 1MB", "1-10MB", "10-100MB", "> 100MB"}

        # Verify all histogram values are non-negative integers
        for _bucket, count in histogram.items():
            assert isinstance(count, int)
            assert count >= 0

        # Verify histogram counts sum to total file count
        histogram_total = sum(histogram.values())
        assert histogram_total == len(snapshot.data_files)
        assert histogram_total == result["total_file_count"]

        # Verify each file is counted in exactly one bucket
        if snapshot.data_files:
            manual_histogram = {
                "< 1MB": 0,
                "1-10MB": 0,
                "10-100MB": 0,
                "> 100MB": 0,
            }

            for file in snapshot.data_files:
                size = file.file_size_bytes
                if size < SIZE_1MB:
                    manual_histogram["< 1MB"] += 1
                elif size < SIZE_10MB:
                    manual_histogram["1-10MB"] += 1
                elif size < SIZE_100MB:
                    manual_histogram["10-100MB"] += 1
                else:
                    manual_histogram["> 100MB"] += 1

            assert histogram == manual_histogram

    @settings(max_examples=100)
    @given(snapshot=snapshot_with_files_strategy())
    def test_property_8_small_file_detection(self, snapshot: SnapshotInfo):
        """Test small file detection.

        For any version, if files smaller than 10MB exist, they should be
        correctly identified and counted.
        """
        result = DeltaForensics.analyze_file_sizes(snapshot)

        # Count small files manually
        expected_small_count = sum(
            1 for file in snapshot.data_files if file.file_size_bytes < SIZE_10MB
        )

        # Verify small file count matches
        assert result["small_file_count"] == expected_small_count

        # Verify small file count is sum of first two histogram buckets
        histogram = result["histogram"]
        assert result["small_file_count"] == histogram["< 1MB"] + histogram["1-10MB"]

        # Verify small file percentage calculation
        if snapshot.data_files:
            expected_percentage = (expected_small_count / len(snapshot.data_files)) * 100.0
            # Allow small floating point differences due to rounding
            assert abs(result["small_file_percentage"] - expected_percentage) < 0.01
        else:
            assert result["small_file_percentage"] == 0.0

    @settings(max_examples=100)
    @given(snapshot=snapshot_with_files_strategy())
    def test_property_9_optimization_opportunity_estimation(self, snapshot: SnapshotInfo):
        """Test optimization opportunity estimation.

        For any version with small files, the estimated file count reduction from
        OPTIMIZE should be less than or equal to the current file count.
        """
        result = DeltaForensics.analyze_file_sizes(snapshot)

        # Optimization opportunity should never exceed total file count
        assert result["optimization_opportunity"] <= result["total_file_count"]

        # Optimization opportunity should never exceed small file count
        assert result["optimization_opportunity"] <= result["small_file_count"]

        # Optimization opportunity should be non-negative
        assert result["optimization_opportunity"] >= 0

        # If there are no small files, optimization opportunity should be 0
        if result["small_file_count"] == 0:
            assert result["optimization_opportunity"] == 0

        # Optimization opportunity should be approximately 80% of small files
        # (allowing for integer rounding)
        expected_opportunity = int(result["small_file_count"] * 0.8)
        assert result["optimization_opportunity"] == expected_opportunity

    @settings(max_examples=100)
    @given(snapshot=snapshot_with_files_strategy())
    def test_size_statistics_correctness(self, snapshot: SnapshotInfo):
        """Verify min, max, median, and total size calculations are correct."""
        result = DeltaForensics.analyze_file_sizes(snapshot)

        if not snapshot.data_files:
            # Empty snapshot should have all zeros
            assert result["min_size_bytes"] == 0
            assert result["max_size_bytes"] == 0
            assert result["median_size_bytes"] == 0
            assert result["total_size_bytes"] == 0
        else:
            file_sizes = [file.file_size_bytes for file in snapshot.data_files]

            # Verify min and max
            assert result["min_size_bytes"] == min(file_sizes)
            assert result["max_size_bytes"] == max(file_sizes)

            # Verify total
            assert result["total_size_bytes"] == sum(file_sizes)

            # Verify median is within range
            assert (
                result["min_size_bytes"] <= result["median_size_bytes"] <= result["max_size_bytes"]
            )

            # Verify median is close to actual median (allowing for integer conversion)
            import statistics

            expected_median = statistics.median(file_sizes)
            assert abs(result["median_size_bytes"] - expected_median) <= 1

    @settings(max_examples=100)
    @given(snapshot=snapshot_with_files_strategy())
    def test_result_structure_completeness(self, snapshot: SnapshotInfo):
        """Verify the result dictionary contains all required keys."""
        result = DeltaForensics.analyze_file_sizes(snapshot)

        # Verify all required keys are present
        required_keys = {
            "histogram",
            "small_file_count",
            "small_file_percentage",
            "optimization_opportunity",
            "min_size_bytes",
            "max_size_bytes",
            "median_size_bytes",
            "total_size_bytes",
            "total_file_count",
        }
        assert set(result.keys()) == required_keys

        # Verify types
        assert isinstance(result["histogram"], dict)
        assert isinstance(result["small_file_count"], int)
        assert isinstance(result["small_file_percentage"], int | float)
        assert isinstance(result["optimization_opportunity"], int)
        assert isinstance(result["min_size_bytes"], int)
        assert isinstance(result["max_size_bytes"], int)
        assert isinstance(result["median_size_bytes"], int)
        assert isinstance(result["total_size_bytes"], int)
        assert isinstance(result["total_file_count"], int)

    @settings(max_examples=100)
    @given(snapshot=snapshot_with_files_strategy())
    def test_percentage_bounds(self, snapshot: SnapshotInfo):
        """Verify small_file_percentage is always between 0 and 100."""
        result = DeltaForensics.analyze_file_sizes(snapshot)

        assert 0.0 <= result["small_file_percentage"] <= 100.0

    @settings(max_examples=100)
    @given(snapshot=snapshot_with_files_strategy())
    def test_idempotency(self, snapshot: SnapshotInfo):
        """Verify calling analyze_file_sizes multiple times produces same result."""
        result1 = DeltaForensics.analyze_file_sizes(snapshot)
        result2 = DeltaForensics.analyze_file_sizes(snapshot)

        assert result1 == result2
