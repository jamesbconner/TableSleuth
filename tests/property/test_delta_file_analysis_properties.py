"""Property-based tests for Delta Lake file analysis.

Tests universal properties of file size distribution, small file detection,
and optimization opportunity estimation.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tablesleuth.models.file_ref import FileRef
from tablesleuth.models.snapshot import SnapshotInfo
from tablesleuth.services.delta_forensics import DeltaForensics


@settings(max_examples=100)
@given(
    file_sizes=st.lists(
        st.integers(min_value=1, max_value=1_000_000_000),  # 1 byte to 1GB
        min_size=1,
        max_size=100,
    )
)
def test_property_file_size_distribution_calculation(file_sizes: list[int]) -> None:
    """Feature: delta-lake-integration, Property 7: File size distribution calculation

    For any version with data files, calculating file size distribution should
    produce a histogram with correct counts for each size bucket.
    """
    # Create FileRef objects from file sizes
    data_files = [
        FileRef(
            path=f"file_{i}.parquet",
            file_size_bytes=size,
            record_count=None,
            source="delta",
            content_type="DATA",
        )
        for i, size in enumerate(file_sizes)
    ]

    # Create snapshot with data files
    snapshot = SnapshotInfo(
        snapshot_id=1,
        parent_id=0,
        timestamp_ms=1705334625000,
        operation="WRITE",
        summary={},
        data_files=data_files,
        delete_files=[],
    )

    # Analyze file sizes
    result = DeltaForensics.analyze_file_sizes(snapshot)

    # Verify histogram exists and has correct structure
    assert "histogram" in result
    histogram = result["histogram"]
    assert isinstance(histogram, dict)

    # Verify all files are accounted for in histogram
    total_in_histogram = sum(histogram.values())
    assert total_in_histogram == len(file_sizes)

    # Verify histogram buckets are correct
    expected_buckets = ["< 1MB", "1-10MB", "10-100MB", "> 100MB"]
    for bucket in expected_buckets:
        assert bucket in histogram
        assert histogram[bucket] >= 0

    # Manually count files in each bucket to verify
    mb = 1024 * 1024

    expected_counts = {
        "< 1MB": sum(1 for s in file_sizes if s < mb),
        "1-10MB": sum(1 for s in file_sizes if mb <= s < 10 * mb),
        "10-100MB": sum(1 for s in file_sizes if 10 * mb <= s < 100 * mb),
        "> 100MB": sum(1 for s in file_sizes if s >= 100 * mb),
    }

    assert histogram == expected_counts


@settings(max_examples=100)
@given(
    small_file_count=st.integers(min_value=0, max_value=50),
    large_file_count=st.integers(min_value=0, max_value=50),
    data=st.data(),
)
def test_property_small_file_detection(
    small_file_count: int, large_file_count: int, data: st.DataObject
) -> None:
    """Feature: delta-lake-integration, Property 8: Small file detection

    For any version, if files smaller than 10MB exist, they should be
    correctly identified and counted.
    """
    # Skip if no files
    if small_file_count == 0 and large_file_count == 0:
        pytest.skip("No files to test")

    mb = 1024 * 1024

    # Create small files (< 10MB) using data.draw()
    small_files = [
        FileRef(
            path=f"small_{i}.parquet",
            file_size_bytes=data.draw(st.integers(min_value=1, max_value=10 * mb - 1)),
            record_count=None,
            source="delta",
            content_type="DATA",
        )
        for i in range(small_file_count)
    ]

    # Create large files (>= 10MB) using data.draw()
    large_files = [
        FileRef(
            path=f"large_{i}.parquet",
            file_size_bytes=data.draw(st.integers(min_value=10 * mb, max_value=1_000_000_000)),
            record_count=None,
            source="delta",
            content_type="DATA",
        )
        for i in range(large_file_count)
    ]

    # Create snapshot
    snapshot = SnapshotInfo(
        snapshot_id=1,
        parent_id=0,
        timestamp_ms=1705334625000,
        operation="WRITE",
        summary={},
        data_files=small_files + large_files,
        delete_files=[],
    )

    # Analyze file sizes
    result = DeltaForensics.analyze_file_sizes(snapshot)

    # Verify small file count
    assert "small_file_count" in result
    assert result["small_file_count"] == small_file_count

    # Verify small file percentage
    assert "small_file_percentage" in result
    total_files = small_file_count + large_file_count
    expected_percentage = (small_file_count / total_files * 100) if total_files > 0 else 0
    assert abs(result["small_file_percentage"] - expected_percentage) < 0.01


@settings(max_examples=100)
@given(file_count=st.integers(min_value=1, max_value=100), data=st.data())
def test_property_optimization_opportunity_estimation(file_count: int, data: st.DataObject) -> None:
    """Feature: delta-lake-integration, Property 9: Optimization opportunity estimation

    For any version with small files, the estimated file count reduction from
    OPTIMIZE should be less than or equal to the current file count.
    """
    mb = 1024 * 1024

    # Create files with random sizes using data.draw()
    data_files = [
        FileRef(
            path=f"file_{i}.parquet",
            file_size_bytes=data.draw(st.integers(min_value=1, max_value=100 * mb)),
            record_count=None,
            source="delta",
            content_type="DATA",
        )
        for i in range(file_count)
    ]

    # Create snapshot
    snapshot = SnapshotInfo(
        snapshot_id=1,
        parent_id=0,
        timestamp_ms=1705334625000,
        operation="WRITE",
        summary={},
        data_files=data_files,
        delete_files=[],
    )

    # Analyze file sizes
    result = DeltaForensics.analyze_file_sizes(snapshot)

    # Verify optimization opportunity exists
    assert "optimization_opportunity" in result
    optimization_opportunity = result["optimization_opportunity"]

    # Property: estimated reduction should be <= current file count
    assert optimization_opportunity <= file_count

    # Property: estimated reduction should be non-negative
    assert optimization_opportunity >= 0

    # Property: if all files are small, opportunity should be significant
    all_small = all(f.file_size_bytes < 10 * mb for f in data_files)
    if all_small and file_count > 1:
        # Should suggest combining files
        assert optimization_opportunity > 0
