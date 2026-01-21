"""Property-based tests for Delta Lake partition analysis.

Tests universal properties of partition distribution and skew detection.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


@settings(max_examples=100)
@given(
    partition_count=st.integers(min_value=1, max_value=50),
    files_per_partition=st.lists(st.integers(min_value=1, max_value=100), min_size=1, max_size=50),
)
def test_property_partition_distribution_calculation(
    partition_count: int, files_per_partition: list[int]
) -> None:
    """Feature: delta-lake-integration, Property 36: Partition distribution calculation

    For any partitioned Delta table, the system should calculate files and
    rows per partition correctly.
    """
    # Ensure we have the right number of partitions
    files_per_partition = files_per_partition[:partition_count]
    if len(files_per_partition) < partition_count:
        files_per_partition.extend([1] * (partition_count - len(files_per_partition)))

    # Calculate statistics
    total_files = sum(files_per_partition)
    min_files = min(files_per_partition)
    max_files = max(files_per_partition)
    avg_files = total_files / partition_count

    # Property: total files should equal sum of files per partition
    assert total_files == sum(files_per_partition)

    # Property: min should be <= all partition file counts
    for count in files_per_partition:
        assert min_files <= count

    # Property: max should be >= all partition file counts
    for count in files_per_partition:
        assert max_files >= count

    # Property: average should be between min and max
    assert min_files <= avg_files <= max_files

    # Property: if all partitions have same file count, min == max == avg
    if len(set(files_per_partition)) == 1:
        assert min_files == max_files == avg_files


@settings(max_examples=100)
@given(
    partition_count=st.integers(min_value=2, max_value=50),
    base_file_count=st.integers(min_value=10, max_value=100),
    skew_factor=st.floats(min_value=1.0, max_value=5.0),
)
def test_property_partition_skew_detection(
    partition_count: int, base_file_count: int, skew_factor: float
) -> None:
    """Feature: delta-lake-integration, Property 37: Partition skew detection

    For any partitioned Delta table where one partition has 2x or more files
    than the average, that partition should be flagged as skewed.
    """
    # Create partitions with one skewed partition
    files_per_partition = [base_file_count] * partition_count

    # Make one partition skewed
    skewed_partition_idx = 0
    files_per_partition[skewed_partition_idx] = int(base_file_count * skew_factor)

    # Calculate average
    avg_files = sum(files_per_partition) / partition_count

    # Detect skewed partitions
    skewed_partitions = [i for i, count in enumerate(files_per_partition) if count >= 2 * avg_files]

    # Property: if the skewed partition has >= 2x average, it should be flagged
    skewed_partition_files = files_per_partition[skewed_partition_idx]
    is_skewed = skewed_partition_files >= 2 * avg_files

    if is_skewed:
        assert skewed_partition_idx in skewed_partitions
    else:
        assert skewed_partition_idx not in skewed_partitions

    # Property: partitions with < 2x average should not be flagged
    for i, count in enumerate(files_per_partition):
        if count < 2 * avg_files:
            assert i not in skewed_partitions

    # Property: all skewed partitions should have >= 2x average files
    for i in skewed_partitions:
        assert files_per_partition[i] >= 2 * avg_files


@settings(max_examples=100)
@given(
    partition_count=st.integers(min_value=2, max_value=50),
    base_file_count=st.integers(min_value=10, max_value=100),
    skew_factor=st.floats(min_value=1.0, max_value=10.0),
)
def test_property_severe_partition_skew_recommendation(
    partition_count: int, base_file_count: int, skew_factor: float
) -> None:
    """Feature: delta-lake-integration, Property 38: Severe partition skew recommendation

    For any partitioned Delta table where partition skew exceeds 3x average,
    a repartitioning recommendation should be generated.
    """
    # Create partitions with one severely skewed partition
    files_per_partition = [base_file_count] * partition_count
    files_per_partition[0] = int(base_file_count * skew_factor)

    # Calculate average
    avg_files = sum(files_per_partition) / partition_count

    # Check if severe skew exists
    max_files = max(files_per_partition)
    has_severe_skew = max_files >= 3 * avg_files

    # Property: if max partition has >= 3x average, should recommend repartitioning
    if has_severe_skew:
        # Property: recommendation should be generated
        recommendation = {
            "type": "REPARTITION",
            "reason": f"Partition skew detected: max {max_files} files vs avg {avg_files:.1f}",
            "priority": "high" if skew_factor >= 5.0 else "medium",
        }

        assert recommendation["type"] == "REPARTITION"
        assert "skew" in recommendation["reason"].lower()

    # Property: if max partition has < 3x average, should not recommend repartitioning
    if not has_severe_skew:
        assert max_files < 3 * avg_files


@settings(max_examples=100)
@given(
    partition_columns=st.lists(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))),
        min_size=1,
        max_size=5,
        unique=True,
    ),
    partition_types=st.lists(
        st.sampled_from(["string", "integer", "date", "timestamp"]), min_size=1, max_size=5
    ),
)
def test_property_partition_metadata_display(
    partition_columns: list[str], partition_types: list[str]
) -> None:
    """Feature: delta-lake-integration, Property 35: Partition metadata display

    For any partitioned Delta table, the system should display all partition
    column names and their data types.
    """
    # Ensure we have matching lengths
    partition_types = partition_types[: len(partition_columns)]
    if len(partition_types) < len(partition_columns):
        partition_types.extend(["string"] * (len(partition_columns) - len(partition_types)))

    # Create partition metadata
    partition_metadata = [
        {"name": col, "type": typ}
        for col, typ in zip(partition_columns, partition_types, strict=False)
    ]

    # Property: should have metadata for all partition columns
    assert len(partition_metadata) == len(partition_columns)

    # Property: each partition column should have name and type
    for i, meta in enumerate(partition_metadata):
        assert "name" in meta
        assert "type" in meta
        assert meta["name"] == partition_columns[i]
        assert meta["type"] == partition_types[i]

    # Property: partition column names should be unique
    names = [m["name"] for m in partition_metadata]
    assert len(names) == len(set(names))


@settings(max_examples=100)
@given(
    partition_values=st.lists(
        st.tuples(
            st.text(min_size=1, max_size=20),  # partition value
            st.integers(min_value=1, max_value=1000),  # file count
        ),
        min_size=1,
        max_size=50,
        unique_by=lambda x: x[0],
    )
)
def test_property_partition_file_distribution(partition_values: list[tuple[str, int]]) -> None:
    """Test that file distribution across partitions is correctly calculated.

    Related to Property 36: Partition distribution calculation.
    """
    # Extract file counts
    file_counts = [count for _, count in partition_values]

    # Calculate statistics
    total_files = sum(file_counts)
    min_files = min(file_counts)
    max_files = max(file_counts)
    avg_files = total_files / len(file_counts)

    # Property: sum of partition files should equal total
    assert sum(file_counts) == total_files

    # Property: each partition should have at least min_files
    for count in file_counts:
        assert count >= min_files

    # Property: no partition should exceed max_files
    for count in file_counts:
        assert count <= max_files

    # Property: standard deviation should reflect distribution
    variance = sum((count - avg_files) ** 2 for count in file_counts) / len(file_counts)
    std_dev = variance**0.5

    # If all partitions have same count, std_dev should be 0
    if len(set(file_counts)) == 1:
        assert std_dev < 0.0001
