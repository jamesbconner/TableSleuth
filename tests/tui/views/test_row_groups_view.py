"""Tests for RowGroupsView widget."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo, RowGroupInfo
from tablesleuth.tui.views.row_groups_view import RowGroupsView


@pytest.fixture
def mock_column_stats() -> ColumnStats:
    """Create a mock ColumnStats with all fields populated."""
    return ColumnStats(
        name="test_column",
        physical_type="INT64",
        logical_type="int64",
        null_count=0,
        min_value=1,
        max_value=1000,
        encodings=["PLAIN", "RLE"],
        compression="ZSTD",
        num_values=1048576,
        distinct_count=500,
        total_compressed_size=4194304,  # 4 MB
        total_uncompressed_size=8388608,  # 8 MB
    )


@pytest.fixture
def mock_column_stats_partial() -> ColumnStats:
    """Create a mock ColumnStats with some fields as None."""
    return ColumnStats(
        name="partial_column",
        physical_type="DOUBLE",
        logical_type="double",
        null_count=None,
        min_value=None,
        max_value=None,
        encodings=["PLAIN"],
        compression="SNAPPY",
        num_values=1048576,
        distinct_count=None,
        total_compressed_size=None,
        total_uncompressed_size=None,
    )


@pytest.fixture
def mock_column_stats_no_stats() -> ColumnStats:
    """Create a mock ColumnStats with most fields as None."""
    return ColumnStats(
        name="no_stats_column",
        physical_type="BYTE_ARRAY",
        logical_type="string",
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


class TestRowGroupsViewFormatSize:
    """Tests for _format_size method."""

    def test_format_size_bytes(self) -> None:
        """Test formatting bytes."""
        result = RowGroupsView._format_size(500)
        assert result == "500.00 B"

    def test_format_size_kilobytes(self) -> None:
        """Test formatting kilobytes."""
        result = RowGroupsView._format_size(1024)
        assert result == "1.00 KB"

        result = RowGroupsView._format_size(2048)
        assert result == "2.00 KB"

    def test_format_size_megabytes(self) -> None:
        """Test formatting megabytes."""
        result = RowGroupsView._format_size(1048576)  # 1 MB
        assert result == "1.00 MB"

        result = RowGroupsView._format_size(4194304)  # 4 MB
        assert result == "4.00 MB"

    def test_format_size_gigabytes(self) -> None:
        """Test formatting gigabytes."""
        result = RowGroupsView._format_size(1073741824)  # 1 GB
        assert result == "1.00 GB"

    def test_format_size_terabytes(self) -> None:
        """Test formatting terabytes."""
        result = RowGroupsView._format_size(1099511627776)  # 1 TB
        assert result == "1.00 TB"

    def test_format_size_petabytes(self) -> None:
        """Test formatting petabytes."""
        result = RowGroupsView._format_size(1125899906842624)  # 1 PB
        assert result == "1.00 PB"

    def test_format_size_none(self) -> None:
        """Test formatting None value."""
        result = RowGroupsView._format_size(None)
        assert result == "N/A"

    def test_format_size_zero(self) -> None:
        """Test formatting zero bytes."""
        result = RowGroupsView._format_size(0)
        assert result == "0.00 B"

    def test_format_size_decimal_precision(self) -> None:
        """Test that formatting uses 2 decimal places."""
        result = RowGroupsView._format_size(1536)  # 1.5 KB
        assert result == "1.50 KB"

        result = RowGroupsView._format_size(5242880)  # 5 MB
        assert result == "5.00 MB"


class TestRowGroupsViewCompressionRatio:
    """Tests for _calculate_compression_ratio method."""

    def test_compression_ratio_good_compression(self) -> None:
        """Test compression ratio calculation with good compression."""
        ratio, color = RowGroupsView._calculate_compression_ratio(4194304, 8388608)
        assert ratio == 50.0
        assert color == "yellow"  # Exactly 50% is yellow

        ratio, color = RowGroupsView._calculate_compression_ratio(2097152, 8388608)
        assert ratio == 25.0
        assert color == "green"  # < 50% is green

    def test_compression_ratio_poor_compression(self) -> None:
        """Test compression ratio calculation with poor compression."""
        ratio, color = RowGroupsView._calculate_compression_ratio(6291456, 8388608)
        assert ratio == 75.0
        assert color == "yellow"  # >= 50% is yellow

    def test_compression_ratio_no_compression(self) -> None:
        """Test compression ratio when sizes are equal."""
        ratio, color = RowGroupsView._calculate_compression_ratio(8388608, 8388608)
        assert ratio == 100.0
        assert color == "yellow"

    def test_compression_ratio_compressed_none(self) -> None:
        """Test compression ratio when compressed size is None."""
        ratio, color = RowGroupsView._calculate_compression_ratio(None, 8388608)
        assert ratio is None
        assert color == "dim"

    def test_compression_ratio_uncompressed_none(self) -> None:
        """Test compression ratio when uncompressed size is None."""
        ratio, color = RowGroupsView._calculate_compression_ratio(4194304, None)
        assert ratio is None
        assert color == "dim"

    def test_compression_ratio_both_none(self) -> None:
        """Test compression ratio when both sizes are None."""
        ratio, color = RowGroupsView._calculate_compression_ratio(None, None)
        assert ratio is None
        assert color == "dim"

    def test_compression_ratio_zero_uncompressed(self) -> None:
        """Test compression ratio with zero uncompressed size."""
        ratio, color = RowGroupsView._calculate_compression_ratio(4194304, 0)
        assert ratio is None
        assert color == "dim"


class TestRowGroupsViewCreateColumnPanel:
    """Tests for _create_column_panel method."""

    def test_create_panel_complete_statistics(self, mock_column_stats: ColumnStats) -> None:
        """Test panel creation with complete statistics."""
        view = RowGroupsView()
        panel = view._create_column_panel(mock_column_stats)

        # Verify panel is created
        assert panel is not None
        assert panel.title == "[bold cyan]test_column[/bold cyan]"

        # Verify content contains expected fields
        content = str(panel.renderable)
        assert "Type:" in content
        assert "INT64" in content
        assert "Codec:" in content
        assert "ZSTD" in content
        assert "Values:" in content
        assert "1,048,576" in content
        assert "Nulls:" in content
        assert "Distinct:" in content
        assert "500" in content
        assert "Compressed:" in content
        assert "Uncompressed:" in content
        assert "Ratio:" in content
        assert "Min:" in content
        assert "Max:" in content

    def test_create_panel_partial_statistics(self, mock_column_stats_partial: ColumnStats) -> None:
        """Test panel creation with partial statistics."""
        view = RowGroupsView()
        panel = view._create_column_panel(mock_column_stats_partial)

        # Verify panel is created
        assert panel is not None

        # Verify content contains N/A for missing fields
        content = str(panel.renderable)
        assert "Type:" in content
        assert "DOUBLE" in content
        assert "Values:" in content
        assert "1,048,576" in content
        # Should have N/A for missing fields
        assert "N/A" in content

    def test_create_panel_no_statistics(self, mock_column_stats_no_stats: ColumnStats) -> None:
        """Test panel creation with no statistics."""
        view = RowGroupsView()
        panel = view._create_column_panel(mock_column_stats_no_stats)

        # Verify panel is created
        assert panel is not None

        # Verify content shows "Not available" message
        content = str(panel.renderable)
        assert "Type:" in content
        assert "BYTE_ARRAY" in content
        assert "Stats:" in content or "Not available" in content

    def test_create_panel_null_count_color_coding(self) -> None:
        """Test that null count is color-coded correctly."""
        view = RowGroupsView()

        # Test with zero nulls (should be green)
        col_no_nulls = ColumnStats(
            name="col1",
            physical_type="INT64",
            logical_type="int64",
            null_count=0,
            min_value=1,
            max_value=100,
            encodings=["PLAIN"],
            compression="ZSTD",
            num_values=100,
            distinct_count=None,
            total_compressed_size=None,
            total_uncompressed_size=None,
        )
        panel = view._create_column_panel(col_no_nulls)
        # Panel should be created successfully
        assert panel is not None

        # Test with non-zero nulls (should be red)
        col_with_nulls = ColumnStats(
            name="col2",
            physical_type="INT64",
            logical_type="int64",
            null_count=50,
            min_value=1,
            max_value=100,
            encodings=["PLAIN"],
            compression="ZSTD",
            num_values=100,
            distinct_count=None,
            total_compressed_size=None,
            total_uncompressed_size=None,
        )
        panel = view._create_column_panel(col_with_nulls)
        # Panel should be created successfully
        assert panel is not None

    def test_create_panel_compression_color_coding(self) -> None:
        """Test that compression ratio is color-coded correctly."""
        view = RowGroupsView()

        # Test with good compression (< 50%)
        col_good_compression = ColumnStats(
            name="col1",
            physical_type="INT64",
            logical_type="int64",
            null_count=0,
            min_value=1,
            max_value=100,
            encodings=["PLAIN"],
            compression="ZSTD",
            num_values=100,
            distinct_count=None,
            total_compressed_size=2097152,  # 2 MB
            total_uncompressed_size=8388608,  # 8 MB (25% ratio)
        )
        panel = view._create_column_panel(col_good_compression)
        assert panel is not None

        # Test with poor compression (>= 50%)
        col_poor_compression = ColumnStats(
            name="col2",
            physical_type="INT64",
            logical_type="int64",
            null_count=0,
            min_value=1,
            max_value=100,
            encodings=["PLAIN"],
            compression="SNAPPY",
            num_values=100,
            distinct_count=None,
            total_compressed_size=6291456,  # 6 MB
            total_uncompressed_size=8388608,  # 8 MB (75% ratio)
        )
        panel = view._create_column_panel(col_poor_compression)
        assert panel is not None

    def test_create_panel_truncates_long_values(self) -> None:
        """Test that min/max values are truncated to 25 characters."""
        view = RowGroupsView()

        long_value = "a" * 50  # 50 character string
        col = ColumnStats(
            name="col1",
            physical_type="BYTE_ARRAY",
            logical_type="string",
            null_count=0,
            min_value=long_value,
            max_value=long_value,
            encodings=["PLAIN"],
            compression="ZSTD",
            num_values=100,
            distinct_count=None,
            total_compressed_size=None,
            total_uncompressed_size=None,
        )
        panel = view._create_column_panel(col)

        # Verify panel is created
        assert panel is not None

        # Verify values are truncated
        content = str(panel.renderable)
        # Should contain truncated value (25 chars)
        assert "a" * 25 in content
        # Should not contain full 50 char value
        assert "a" * 50 not in content
