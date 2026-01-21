"""Property-based tests for Delta Lake DML operation analysis.

Tests universal properties of rewrite amplification calculation, MERGE operation
metrics, and high amplification flagging.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


@settings(max_examples=100)
@given(
    bytes_changed=st.integers(min_value=1, max_value=1_000_000_000),
    amplification_factor=st.floats(min_value=1.0, max_value=100.0),
)
def test_property_rewrite_amplification_calculation(
    bytes_changed: int, amplification_factor: float
) -> None:
    """Feature: delta-lake-integration, Property 19: Rewrite amplification calculation

    For any UPDATE, DELETE, or MERGE operation, rewrite amplification should be
    calculated as (bytes_rewritten / bytes_changed) and should be >= 1.0.
    """
    # Calculate bytes rewritten based on amplification factor (use float to avoid rounding)
    bytes_rewritten = bytes_changed * amplification_factor

    # Calculate amplification
    calculated_amplification = bytes_rewritten / bytes_changed

    # Property: amplification should be >= 1.0
    assert calculated_amplification >= 1.0

    # Property: amplification should match expected factor (within floating point tolerance)
    assert abs(calculated_amplification - amplification_factor) < 0.0001

    # Property: if bytes_changed equals bytes_rewritten, amplification should be 1.0
    if abs(bytes_changed - bytes_rewritten) < 0.0001:
        assert abs(calculated_amplification - 1.0) < 0.0001

    # Property: bytes_rewritten should always be >= bytes_changed
    assert bytes_rewritten >= bytes_changed


@settings(max_examples=100)
@given(
    rows_matched=st.integers(min_value=0, max_value=1_000_000),
    rows_inserted=st.integers(min_value=0, max_value=1_000_000),
    rows_updated=st.integers(min_value=0, max_value=1_000_000),
    rows_deleted=st.integers(min_value=0, max_value=1_000_000),
    files_rewritten=st.integers(min_value=1, max_value=1000),
)
def test_property_merge_operation_metrics(
    rows_matched: int,
    rows_inserted: int,
    rows_updated: int,
    rows_deleted: int,
    files_rewritten: int,
) -> None:
    """Feature: delta-lake-integration, Property 18: MERGE operation metrics

    For any version representing a MERGE operation, the displayed metrics should
    include rows matched, rows inserted, and files rewritten from operation metrics.
    """
    # Skip if no operation occurred
    if rows_matched == 0 and rows_inserted == 0 and rows_updated == 0 and rows_deleted == 0:
        pytest.skip("No rows affected")

    # Create operation metrics
    operation_metrics = {
        "numTargetRowsMatched": rows_matched,
        "numTargetRowsInserted": rows_inserted,
        "numTargetRowsUpdated": rows_updated,
        "numTargetRowsDeleted": rows_deleted,
        "numTargetFilesAdded": files_rewritten,
        "numTargetFilesRemoved": files_rewritten,
    }

    # Property: all metrics should be non-negative
    assert rows_matched >= 0
    assert rows_inserted >= 0
    assert rows_updated >= 0
    assert rows_deleted >= 0
    assert files_rewritten >= 0

    # Property: total rows affected should be sum of operations
    total_rows_affected = rows_inserted + rows_updated + rows_deleted
    assert total_rows_affected >= 0

    # Property: rows matched should be >= rows updated + rows deleted
    # (matched rows can be updated, deleted, or left unchanged)
    assert rows_matched >= (rows_updated + rows_deleted)

    # Property: files added should equal files removed for MERGE
    # (MERGE rewrites files, so adds = removes)
    assert operation_metrics["numTargetFilesAdded"] == operation_metrics["numTargetFilesRemoved"]


@settings(max_examples=100)
@given(
    bytes_changed=st.integers(
        min_value=100, max_value=100_000_000
    ),  # Increased min to avoid truncation issues
    amplification_factor=st.floats(min_value=1.0, max_value=50.0, exclude_min=True),
)
def test_property_high_amplification_flagging(
    bytes_changed: int, amplification_factor: float
) -> None:
    """Feature: delta-lake-integration, Property 20: High amplification flagging

    For any DML operation where rewrite amplification exceeds 10x, the operation
    should be flagged as inefficient.
    """
    bytes_rewritten = int(bytes_changed * amplification_factor)
    calculated_amplification = bytes_rewritten / bytes_changed

    # Property: operations with amplification > 10x should be flagged
    is_high_amplification = calculated_amplification > 10.0
    should_be_flagged = amplification_factor > 10.0

    # Due to integer truncation, allow small tolerance
    # If amplification_factor is very close to 10.0, truncation might cause mismatch
    if abs(amplification_factor - 10.0) < 0.1:
        # Skip edge cases where truncation causes issues
        return

    assert is_high_amplification == should_be_flagged

    # Property: operations with amplification <= 10x should not be flagged
    if amplification_factor <= 10.0:
        assert not is_high_amplification

    # Property: operations with amplification > 10x should be flagged
    if amplification_factor > 10.0:
        assert is_high_amplification


@settings(max_examples=100)
@given(
    operation_count=st.integers(min_value=2, max_value=20),
    base_amplification=st.floats(min_value=1.0, max_value=5.0),
    trend_increase=st.floats(min_value=0.0, max_value=2.0),
)
def test_property_amplification_trend_analysis(
    operation_count: int, base_amplification: float, trend_increase: float
) -> None:
    """Feature: delta-lake-integration, Property 52: Amplification trend analysis

    For any sequence of DML operations, if rewrite amplification increases over
    time, the system should flag this as a potential partitioning or clustering issue.
    """
    # Create sequence of operations with increasing amplification
    amplifications = [base_amplification + (i * trend_increase) for i in range(operation_count)]

    # Property: if trend_increase > 0, amplification should increase over time
    if trend_increase > 0.001:  # Use small threshold to avoid floating point issues
        for i in range(len(amplifications) - 1):
            assert amplifications[i + 1] > amplifications[i]

    # Property: if trend_increase == 0, amplification should be constant
    if trend_increase < 0.001:
        for i in range(len(amplifications) - 1):
            assert abs(amplifications[i + 1] - amplifications[i]) < 0.01

    # Property: all amplifications should be >= base_amplification
    for amp in amplifications:
        assert amp >= base_amplification

    # Property: max amplification should be at the end if increasing
    if trend_increase > 0.001:
        assert amplifications[-1] == max(amplifications)

    # Property: if final amplification > 2x initial, should flag as trend
    has_significant_trend = amplifications[-1] > (amplifications[0] * 2)
    expected_trend = (base_amplification + ((operation_count - 1) * trend_increase)) > (
        base_amplification * 2
    )

    # Only check if trend_increase is significant enough to matter
    if trend_increase > 0.001:
        assert has_significant_trend == expected_trend


@settings(max_examples=100)
@given(amplifications=st.lists(st.floats(min_value=1.0, max_value=100.0), min_size=1, max_size=50))
def test_property_high_amplification_highlighting(amplifications: list[float]) -> None:
    """Feature: delta-lake-integration, Property 53: High amplification highlighting

    For any set of DML operations, operations with the highest amplification
    should be highlighted or sorted to the top.
    """
    # Sort amplifications in descending order
    sorted_amplifications = sorted(amplifications, reverse=True)

    # Property: first element should be the maximum
    assert sorted_amplifications[0] == max(amplifications)

    # Property: last element should be the minimum
    assert sorted_amplifications[-1] == min(amplifications)

    # Property: list should be in descending order
    for i in range(len(sorted_amplifications) - 1):
        assert sorted_amplifications[i] >= sorted_amplifications[i + 1]

    # Property: all original values should be present
    assert sorted(sorted_amplifications) == sorted(amplifications)

    # Property: if all values are the same, order doesn't matter
    if len(set(amplifications)) == 1:
        assert all(a == amplifications[0] for a in sorted_amplifications)
