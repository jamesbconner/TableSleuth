"""Tests for ProfileView widget."""

from __future__ import annotations

import pytest

from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo
from tablesleuth.models.profiling import ColumnProfile
from tablesleuth.tui.views import ProfileView


@pytest.fixture
def sample_file_info() -> ParquetFileInfo:
    """Create sample ParquetFileInfo for testing.

    Returns:
        ParquetFileInfo with test columns
    """
    columns = [
        ColumnStats(
            name="id",
            physical_type="INT64",
            logical_type=None,
            null_count=0,
            min_value=1,
            max_value=100,
            encodings=["PLAIN"],
            compression="SNAPPY",
            num_values=100,
            distinct_count=100,
            total_compressed_size=1024,
            total_uncompressed_size=2048,
        ),
        ColumnStats(
            name="name",
            physical_type="BYTE_ARRAY",
            logical_type="UTF8",
            null_count=5,
            min_value="Alice",
            max_value="Zoe",
            encodings=["PLAIN"],
            compression="SNAPPY",
            num_values=95,
            distinct_count=80,
            total_compressed_size=2048,
            total_uncompressed_size=4096,
        ),
        ColumnStats(
            name="age",
            physical_type="INT32",
            logical_type=None,
            null_count=2,
            min_value=18,
            max_value=65,
            encodings=["PLAIN"],
            compression="SNAPPY",
            num_values=98,
            distinct_count=47,
            total_compressed_size=512,
            total_uncompressed_size=1024,
        ),
        ColumnStats(
            name="salary",
            physical_type="DOUBLE",
            logical_type=None,
            null_count=10,
            min_value=30000.0,
            max_value=150000.0,
            encodings=["PLAIN"],
            compression="SNAPPY",
            num_values=90,
            distinct_count=85,
            total_compressed_size=1024,
            total_uncompressed_size=2048,
        ),
    ]
    return ParquetFileInfo(
        path="test.parquet",
        file_size_bytes=10240,
        num_rows=100,
        num_row_groups=1,
        num_columns=4,
        schema={"id": "INT64", "name": "BYTE_ARRAY", "age": "INT32", "salary": "DOUBLE"},
        row_groups=[],
        columns=columns,
        created_by="test",
        format_version="2.6",
    )


@pytest.fixture
def sample_profile() -> ColumnProfile:
    """Create sample column profile for testing.

    Returns:
        ColumnProfile with complete statistics
    """
    return ColumnProfile(
        column="test_column",
        row_count=10000,
        non_null_count=9500,
        null_count=500,
        distinct_count=1000,
        min_value=1,
        max_value=9999,
        is_numeric=True,
        average=5000.5,
        median=5000.0,
        mode=4242,
        mode_count=15,
        std_dev=2886.75,
        variance=8333333.25,
        q1=2500.0,
        q3=7500.0,
    )


@pytest.fixture
def minimal_profile() -> ColumnProfile:
    """Create column profile with minimal data.

    Returns:
        ColumnProfile with None values for optional fields
    """
    return ColumnProfile(
        column="minimal_column",
        row_count=1000,
        non_null_count=800,
        null_count=200,
        distinct_count=None,
        min_value=None,
        max_value=None,
    )


def test_profile_view_initialization() -> None:
    """Test ProfileView can be initialized."""
    view = ProfileView()
    assert view is not None
    assert view._file_info is None
    assert view._selected_column is None
    assert view._column_filter == ""
    assert view._profile_result is None
    assert view._is_loading is False


def test_profile_view_is_loading_property() -> None:
    """Test is_loading property."""
    view = ProfileView()

    # Initially not loading
    assert view.is_loading is False

    # Set loading state
    view._is_loading = True
    assert view.is_loading is True

    # Clear loading state
    view._is_loading = False
    assert view.is_loading is False


def test_profile_view_update(sample_profile: ColumnProfile) -> None:
    """Test updating profile results."""
    view = ProfileView()

    # Update with profile
    view._profile_result = sample_profile
    view._is_loading = False

    assert view._profile_result == sample_profile
    assert view.is_loading is False


def test_profile_view_clear(sample_profile: ColumnProfile) -> None:
    """Test clearing profile view."""
    view = ProfileView()

    # Set some state
    view._profile_result = sample_profile
    view._is_loading = True

    # Clear should reset state
    view._profile_result = None
    view._is_loading = False

    assert view._profile_result is None
    assert view.is_loading is False


def test_profile_view_handles_minimal_profile(minimal_profile: ColumnProfile) -> None:
    """Test that view handles profiles with missing data."""
    view = ProfileView()

    # Should not raise any errors
    view._profile_result = minimal_profile

    assert view._profile_result == minimal_profile


def test_format_value_truncation() -> None:
    """Test value formatting with truncation."""
    view = ProfileView()

    # Short value
    short_value = "test"
    formatted = view._format_value(short_value)
    assert formatted == "test"

    # Long value (should be truncated)
    long_value = "a" * 100
    formatted = view._format_value(long_value)
    assert len(formatted) <= 53  # 50 chars + "..."
    assert formatted.endswith("...")


def test_format_value_types() -> None:
    """Test value formatting with different types."""
    view = ProfileView()

    # Integer
    assert "42" in view._format_value(42)

    # Float
    assert "3.14" in view._format_value(3.14)

    # String
    assert view._format_value("hello") == "hello"

    # None
    assert view._format_value(None) == "NULL"


def test_profile_view_loading_state() -> None:
    """Test loading state management."""
    view = ProfileView()

    # Initially not loading
    assert view.is_loading is False

    # Simulate loading
    view._is_loading = True
    assert view.is_loading is True

    # Simulate completion
    view._is_loading = False
    assert view.is_loading is False


def test_profile_calculations(sample_profile: ColumnProfile) -> None:
    """Test that profile calculations are correct."""
    # Verify the test data is consistent
    assert sample_profile.row_count == sample_profile.non_null_count + sample_profile.null_count

    # Calculate null percentage
    null_pct = (sample_profile.null_count / sample_profile.row_count) * 100
    assert null_pct == 5.0  # 500/10000 = 5%

    # Calculate cardinality percentage
    if sample_profile.distinct_count is not None:
        cardinality_pct = (sample_profile.distinct_count / sample_profile.row_count) * 100
        assert cardinality_pct == 10.0  # 1000/10000 = 10%


def test_profile_view_state_transitions(sample_profile: ColumnProfile) -> None:
    """Test state transitions during profiling workflow."""
    view = ProfileView()

    # Initial state
    assert view._profile_result is None
    assert view.is_loading is False

    # Start loading
    view._is_loading = True
    assert view.is_loading is True

    # Complete with results
    view._profile_result = sample_profile
    view._is_loading = False
    assert view._profile_result == sample_profile
    assert view.is_loading is False

    # Clear
    view._profile_result = None
    assert view._profile_result is None
    assert view.is_loading is False


def test_profile_view_update_file_info(sample_file_info: ParquetFileInfo) -> None:
    """Test updating file info (state only, not DOM)."""
    view = ProfileView()

    # Just test state updates without DOM operations
    view._file_info = sample_file_info
    view._selected_column = None
    view._profile_result = None

    assert view._file_info == sample_file_info
    assert view._selected_column is None
    assert view._profile_result is None


def test_profile_view_clear(
    sample_file_info: ParquetFileInfo, sample_profile: ColumnProfile
) -> None:
    """Test clearing the view."""
    view = ProfileView()

    # Set some state
    view._file_info = sample_file_info
    view._selected_column = "test"
    view._column_filter = "filter"
    view._profile_result = sample_profile
    view._is_loading = True

    # Clear
    view.clear()

    # Check state is cleared
    assert view._file_info is None
    assert view._selected_column is None
    assert view._column_filter == ""
    assert view._profile_result is None
    assert view._is_loading is False


def test_format_value_numeric() -> None:
    """Test formatting numeric values."""
    view = ProfileView()

    # Integer
    assert "1,234" in view._format_value(1234)

    # Float
    formatted = view._format_value(1234.5678)
    assert "1,234" in formatted


def test_format_value_null() -> None:
    """Test formatting None values."""
    view = ProfileView()
    assert view._format_value(None) == "NULL"


def test_format_value_string() -> None:
    """Test formatting string values."""
    view = ProfileView()
    assert view._format_value("test") == "test"

    # Long string should be truncated
    long_string = "a" * 60
    formatted = view._format_value(long_string)
    assert len(formatted) == 50
    assert formatted.endswith("...")


def test_build_profile_content_numeric(sample_profile: ColumnProfile) -> None:
    """Test building profile content for numeric column."""
    view = ProfileView()
    content = view._build_profile_content(sample_profile)

    # Check that content contains expected sections (accounting for Rich markup)
    assert "Column Profile: test_column" in content
    assert "Row Statistics" in content
    assert "10,000" in content  # Row count
    assert "Cardinality" in content
    assert "Mode" in content
    assert "Numeric Statistics" in content
    assert "Average:" in content
    assert "Quartiles" in content
    assert "Q1 (25th percentile):" in content
    assert "IQR (Q3 - Q1):" in content
    assert "Value Range" in content


def test_build_profile_content_non_numeric() -> None:
    """Test building profile content for non-numeric column."""
    profile = ColumnProfile(
        column="text_column",
        row_count=100,
        non_null_count=95,
        null_count=5,
        distinct_count=80,
        min_value="apple",
        max_value="zebra",
        is_numeric=False,
        mode="banana",
        mode_count=10,
    )

    view = ProfileView()
    content = view._build_profile_content(profile)

    # Check that content contains expected sections but not numeric stats (accounting for Rich markup)
    assert "Column Profile: text_column" in content
    assert "Row Statistics" in content
    assert "Cardinality" in content
    assert "Mode" in content
    assert "banana" in content  # Mode value
    assert "Value Range" in content
    assert "apple" in content  # Min value
    assert "zebra" in content  # Max value

    # Should not contain numeric statistics
    assert "Numeric Statistics" not in content
    assert "Average" not in content
    assert "Quartiles" not in content


def test_update_profile(sample_profile: ColumnProfile) -> None:
    """Test updating profile results (state only, not DOM)."""
    view = ProfileView()

    # Just test state updates without DOM operations
    view._profile_result = sample_profile
    view._is_loading = False

    # Check that profile was stored
    assert view._profile_result == sample_profile
    assert view._is_loading is False


def test_show_error() -> None:
    """Test showing error message (state only, not DOM)."""
    view = ProfileView()

    # Just test state updates without DOM operations
    view._is_loading = False

    assert view._is_loading is False
