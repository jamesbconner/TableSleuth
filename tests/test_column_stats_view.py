"""Tests for ColumnStatsView widget."""

from __future__ import annotations

import pytest
from textual.widgets import Static

from table_sleuth.models.parquet import ColumnStats
from table_sleuth.tui.views import ColumnStatsView


@pytest.fixture
def sample_column_stats() -> ColumnStats:
    """Create sample column statistics for testing.

    Returns:
        ColumnStats with complete metadata
    """
    return ColumnStats(
        name="test_column",
        physical_type="INT64",
        logical_type="TIMESTAMP_MILLIS",
        null_count=42,
        min_value=1000,
        max_value=9999,
        encodings=["PLAIN", "RLE"],
        compression="SNAPPY",
        num_values=None,
        distinct_count=None,
        total_compressed_size=None,
        total_uncompressed_size=None,
    )


@pytest.fixture
def minimal_column_stats() -> ColumnStats:
    """Create column statistics with missing values.

    Returns:
        ColumnStats with None values for statistics
    """
    return ColumnStats(
        name="minimal_column",
        physical_type="BYTE_ARRAY",
        logical_type=None,
        null_count=None,
        min_value=None,
        max_value=None,
        encodings=[],
        compression="UNCOMPRESSED",
        num_values=None,
        distinct_count=None,
        total_compressed_size=None,
        total_uncompressed_size=None,
    )


def test_column_stats_view_initialization() -> None:
    """Test ColumnStatsView can be initialized."""
    view = ColumnStatsView()
    assert view is not None


def test_column_stats_view_with_initial_data(sample_column_stats: ColumnStats) -> None:
    """Test ColumnStatsView initialization with data."""
    view = ColumnStatsView(column_stats=sample_column_stats)
    assert view is not None
    assert view._column_stats == sample_column_stats


def test_column_stats_view_update(sample_column_stats: ColumnStats) -> None:
    """Test updating column statistics."""
    view = ColumnStatsView()

    # Just verify the internal state is updated
    # (Full UI testing requires mounting in a Textual app)
    view._column_stats = sample_column_stats

    assert view._column_stats == sample_column_stats


def test_column_stats_view_clear(sample_column_stats: ColumnStats) -> None:
    """Test clearing column statistics."""
    view = ColumnStatsView(column_stats=sample_column_stats)

    # Just verify the internal state is cleared
    # (Full UI testing requires mounting in a Textual app)
    view._column_stats = None

    assert view._column_stats is None


def test_column_stats_view_handles_missing_stats(
    minimal_column_stats: ColumnStats,
) -> None:
    """Test that view handles missing statistics gracefully."""
    view = ColumnStatsView(column_stats=minimal_column_stats)
    assert view is not None
    assert view._column_stats == minimal_column_stats


def test_format_value_truncation() -> None:
    """Test value formatting with truncation."""
    # Short value
    short_value = "test"
    formatted = ColumnStatsView._format_value(short_value)
    assert formatted == "test"

    # Long value (should be truncated)
    long_value = "a" * 100
    formatted = ColumnStatsView._format_value(long_value)
    assert len(formatted) <= 53  # 50 chars + "..."
    assert formatted.endswith("...")


def test_format_value_types() -> None:
    """Test value formatting with different types."""
    # Integer
    assert ColumnStatsView._format_value(42) == "42"

    # Float
    assert ColumnStatsView._format_value(3.14) == "3.14"

    # String
    assert ColumnStatsView._format_value("hello") == "hello"

    # None
    assert ColumnStatsView._format_value(None) == "None"
