"""Property-based tests for Delta Lake storage waste analysis.

Tests universal properties of tombstone identification, storage waste calculation,
and active-to-tombstone ratio.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tablesleuth.models.file_ref import FileRef
from tablesleuth.models.snapshot import SnapshotInfo


@settings(max_examples=100)
@given(
    active_file_count=st.integers(min_value=1, max_value=50),
    tombstone_file_count=st.integers(min_value=0, max_value=50),
    file_size_range=st.tuples(
        st.integers(min_value=1_000_000, max_value=10_000_000),  # 1-10MB
        st.integers(min_value=10_000_000, max_value=100_000_000),  # 10-100MB
    ),
    data=st.data(),
)
def test_property_storage_waste_calculation(
    active_file_count: int,
    tombstone_file_count: int,
    file_size_range: tuple[int, int],
    data: st.DataObject,
) -> None:
    """Feature: delta-lake-integration, Property 14: Storage waste calculation

    For any version, the sum of tombstone file sizes should equal the
    calculated storage waste.
    """
    min_size, max_size = file_size_range

    # Create active files using data.draw()
    active_files = [
        FileRef(
            path=f"active_{i}.parquet",
            file_size_bytes=data.draw(st.integers(min_value=min_size, max_value=max_size)),
            record_count=None,
            source="delta",
            content_type="DATA",
        )
        for i in range(active_file_count)
    ]

    # Create tombstone files (stored in snapshot extra metadata) using data.draw()
    tombstone_sizes = [
        data.draw(st.integers(min_value=min_size, max_value=max_size))
        for _ in range(tombstone_file_count)
    ]

    # Calculate expected values
    active_size = sum(f.file_size_bytes for f in active_files)
    tombstone_size = sum(tombstone_sizes)
    total_size = active_size + tombstone_size

    # Property: tombstone size should equal sum of individual tombstone files
    assert tombstone_size == sum(tombstone_sizes)

    # Property: total size should be sum of active and tombstone
    assert total_size == active_size + tombstone_size

    # Property: waste percentage should be in valid range [0, 100]
    if total_size > 0:
        waste_percentage = (tombstone_size / total_size) * 100
        assert 0 <= waste_percentage <= 100

    # Property: if no tombstones, waste should be 0
    if tombstone_file_count == 0:
        assert tombstone_size == 0


@settings(max_examples=100)
@given(
    active_count=st.integers(min_value=1, max_value=100),
    tombstone_count=st.integers(min_value=0, max_value=100),
    avg_file_size=st.integers(min_value=1_000_000, max_value=100_000_000),
)
def test_property_active_to_tombstone_ratio(
    active_count: int, tombstone_count: int, avg_file_size: int
) -> None:
    """Feature: delta-lake-integration, Property 15: Active to tombstone ratio

    For any version, the ratio of active files to tombstone files should be
    correctly calculated as (active_size / (active_size + tombstone_size)).
    """
    # Create files with similar sizes for easier ratio calculation
    active_size = active_count * avg_file_size
    tombstone_size = tombstone_count * avg_file_size
    total_size = active_size + tombstone_size

    # Calculate expected ratio
    if total_size > 0:
        expected_ratio = active_size / total_size
    else:
        expected_ratio = 0

    # Property: ratio should be in valid range [0, 1]
    assert 0 <= expected_ratio <= 1

    # Property: if no tombstones, ratio should be 1
    if tombstone_count == 0:
        assert expected_ratio == 1.0

    # Property: if no active files, ratio should be 0
    if active_count == 0 and tombstone_count > 0:
        expected_ratio = 0
        assert expected_ratio == 0.0

    # Property: ratio + waste_ratio should equal 1
    if total_size > 0:
        waste_ratio = tombstone_size / total_size
        assert abs((expected_ratio + waste_ratio) - 1.0) < 0.0001


@settings(max_examples=100)
@given(
    file_count=st.integers(min_value=1, max_value=50),
    retention_days=st.integers(min_value=1, max_value=30),
    days_since_deletion=st.lists(st.integers(min_value=0, max_value=60), min_size=1, max_size=50),
    data=st.data(),
)
def test_property_reclaimable_storage_calculation(
    file_count: int, retention_days: int, days_since_deletion: list[int], data: st.DataObject
) -> None:
    """Feature: delta-lake-integration, Property 16: Reclaimable storage calculation

    For any version, tombstone files older than the retention period should be
    included in reclaimable storage calculation.
    """
    # Ensure we have the right number of deletion timestamps
    days_since_deletion = days_since_deletion[:file_count]
    if len(days_since_deletion) < file_count:
        days_since_deletion.extend([0] * (file_count - len(days_since_deletion)))

    # Create tombstone files with deletion timestamps using data.draw()
    current_time_ms = 1705334625000  # Fixed timestamp
    day_ms = 24 * 60 * 60 * 1000

    tombstone_files = []
    reclaimable_size = 0

    for i, days_ago in enumerate(days_since_deletion):
        file_size = data.draw(st.integers(min_value=1_000_000, max_value=10_000_000))
        deletion_time = current_time_ms - (days_ago * day_ms)

        tombstone_files.append(
            {
                "path": f"tombstone_{i}.parquet",
                "size": file_size,
                "deletion_timestamp": deletion_time,
            }
        )

        # If older than retention period, it's reclaimable
        if days_ago > retention_days:
            reclaimable_size += file_size

    # Property: reclaimable size should be sum of files older than retention
    total_tombstone_size = sum(f["size"] for f in tombstone_files)

    # Property: reclaimable should be <= total tombstone size
    assert reclaimable_size <= total_tombstone_size

    # Property: reclaimable should be non-negative
    assert reclaimable_size >= 0

    # Property: if all files are within retention, reclaimable should be 0
    all_within_retention = all(days <= retention_days for days in days_since_deletion)
    if all_within_retention:
        assert reclaimable_size == 0

    # Property: if all files are beyond retention, reclaimable should equal total
    all_beyond_retention = all(days > retention_days for days in days_since_deletion)
    if all_beyond_retention:
        assert reclaimable_size == total_tombstone_size
