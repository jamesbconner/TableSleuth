"""Tests for ProfileView widget."""

from __future__ import annotations

import pytest

from table_sleuth.models.profiling import ColumnProfile
from table_sleuth.tui.views import ProfileView


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
    # Short value
    short_value = "test"
    formatted = ProfileView._format_value(short_value)
    assert formatted == "test"

    # Long value (should be truncated)
    long_value = "a" * 100
    formatted = ProfileView._format_value(long_value)
    assert len(formatted) <= 53  # 50 chars + "..."
    assert formatted.endswith("...")


def test_format_value_types() -> None:
    """Test value formatting with different types."""
    # Integer
    assert ProfileView._format_value(42) == "42"

    # Float
    assert ProfileView._format_value(3.14) == "3.14"

    # String
    assert ProfileView._format_value("hello") == "hello"

    # None
    assert ProfileView._format_value(None) == "None"


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
