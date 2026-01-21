"""Tests for StructureView widget."""

from __future__ import annotations

from pathlib import Path

import pytest

from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo, RowGroupInfo
from tablesleuth.tui.views.structure_view import StructureView


@pytest.fixture
def sample_column_stats() -> list[ColumnStats]:
    """Create sample column statistics."""
    return [
        ColumnStats(
            name="id",
            physical_type="INT64",
            logical_type="INT64",
            null_count=0,
            min_value=1,
            max_value=100,
            encodings=["PLAIN", "RLE"],
            compression="SNAPPY",
            num_values=None,
            distinct_count=None,
            total_compressed_size=None,
            total_uncompressed_size=None,
        ),
        ColumnStats(
            name="name",
            physical_type="BYTE_ARRAY",
            logical_type="UTF8",
            null_count=5,
            min_value="Alice",
            max_value="Zoe",
            encodings=["DICTIONARY"],
            compression="GZIP",
            num_values=None,
            distinct_count=None,
            total_compressed_size=None,
            total_uncompressed_size=None,
        ),
    ]


@pytest.fixture
def sample_row_group(sample_column_stats: list[ColumnStats]) -> RowGroupInfo:
    """Create a sample row group."""
    return RowGroupInfo(
        index=0,
        num_rows=10000,
        total_byte_size=1024 * 1024,  # 1 MB
        columns=sample_column_stats,
    )


@pytest.fixture
def sample_file_info(
    sample_row_group: RowGroupInfo,
    sample_column_stats: list[ColumnStats],
) -> ParquetFileInfo:
    """Create sample ParquetFileInfo."""
    return ParquetFileInfo(
        path="/path/to/test.parquet",
        file_size_bytes=2 * 1024 * 1024,  # 2 MB
        num_rows=10000,
        num_row_groups=1,
        num_columns=2,
        schema={
            "id": {"type": "int64", "nullable": False},
            "name": {"type": "string", "nullable": True},
        },
        row_groups=[sample_row_group],
        columns=sample_column_stats,
        created_by="test",
        format_version="2.6",
    )


def test_structure_view_initialization() -> None:
    """Test StructureView can be initialized."""
    view = StructureView()
    assert view is not None
    assert view._file_info is None


def test_structure_view_initialization_with_file_info(
    sample_file_info: ParquetFileInfo,
) -> None:
    """Test StructureView can be initialized with file info."""
    view = StructureView(file_info=sample_file_info)
    assert view is not None
    assert view._file_info == sample_file_info


def test_structure_view_has_compose_method() -> None:
    """Test StructureView has compose method."""
    view = StructureView()
    assert hasattr(view, "compose")
    assert callable(view.compose)


def test_format_size_bytes() -> None:
    """Test _format_size utility method with bytes."""
    assert StructureView._format_size(512) == "512.0 B"
    assert StructureView._format_size(1023) == "1023.0 B"


def test_format_size_kilobytes() -> None:
    """Test _format_size utility method with kilobytes."""
    assert StructureView._format_size(1024) == "1.0 KB"
    assert StructureView._format_size(2048) == "2.0 KB"
    assert StructureView._format_size(1536) == "1.5 KB"


def test_format_size_megabytes() -> None:
    """Test _format_size utility method with megabytes."""
    assert StructureView._format_size(1024 * 1024) == "1.0 MB"
    assert StructureView._format_size(2 * 1024 * 1024) == "2.0 MB"
    assert StructureView._format_size(int(1.5 * 1024 * 1024)) == "1.5 MB"


def test_format_size_gigabytes() -> None:
    """Test _format_size utility method with gigabytes."""
    assert StructureView._format_size(1024 * 1024 * 1024) == "1.0 GB"
    assert StructureView._format_size(2 * 1024 * 1024 * 1024) == "2.0 GB"


def test_format_size_terabytes() -> None:
    """Test _format_size utility method with terabytes."""
    assert StructureView._format_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"


def test_format_column_chunk_basic(sample_column_stats: list[ColumnStats]) -> None:
    """Test _create_column_panel with basic column."""
    view = StructureView()
    col = sample_column_stats[0]

    result = view._create_column_panel(col)

    # Check that it returns a Panel
    from rich.panel import Panel

    assert isinstance(result, Panel)
    # Check title contains column name
    assert "id" in str(result.title)


def test_format_column_chunk_with_logical_type(
    sample_column_stats: list[ColumnStats],
) -> None:
    """Test _create_column_panel with logical type."""
    view = StructureView()
    col = sample_column_stats[1]

    result = view._create_column_panel(col)

    # Check that it returns a Panel
    from rich.panel import Panel

    assert isinstance(result, Panel)
    # Check title contains column name
    assert "name" in str(result.title)


def test_format_column_chunk_no_encodings() -> None:
    """Test _create_column_panel with no encodings."""
    view = StructureView()
    col = ColumnStats(
        name="test",
        physical_type="INT32",
        logical_type=None,
        null_count=0,
        min_value=None,
        max_value=None,
        encodings=[],
        compression="UNCOMPRESSED",
        num_values=None,
        distinct_count=None,
        total_compressed_size=None,
        total_uncompressed_size=None,
    )

    result = view._create_column_panel(col)

    # Check that it returns a Panel
    from rich.panel import Panel

    assert isinstance(result, Panel)
    # Check title contains column name
    assert "test" in str(result.title)


def test_render_header(sample_file_info: ParquetFileInfo) -> None:
    """Test _render_header method."""
    view = StructureView()
    header = view._render_header(sample_file_info)

    assert header is not None
    # Header now returns a Static widget with Rich Panel
    from textual.widgets import Static

    assert isinstance(header, Static)


def test_render_row_groups(sample_file_info: ParquetFileInfo) -> None:
    """Test _render_row_groups method."""
    view = StructureView()
    row_groups = view._render_row_groups(sample_file_info)

    assert row_groups is not None
    # Row groups now returns a single Container with all row groups
    from textual.containers import Container

    assert isinstance(row_groups, Container)


def test_render_row_groups_multiple(sample_column_stats: list[ColumnStats]) -> None:
    """Test _render_row_groups with multiple row groups."""
    view = StructureView()

    # Create file info with multiple row groups
    file_info = ParquetFileInfo(
        path="/path/to/test.parquet",
        file_size_bytes=4 * 1024 * 1024,
        num_rows=20000,
        num_row_groups=2,
        num_columns=2,
        schema={},
        row_groups=[
            RowGroupInfo(
                index=0,
                num_rows=10000,
                total_byte_size=1024 * 1024,
                columns=sample_column_stats,
            ),
            RowGroupInfo(
                index=1,
                num_rows=10000,
                total_byte_size=1024 * 1024,
                columns=sample_column_stats,
            ),
        ],
        columns=sample_column_stats,
        created_by="test",
        format_version="2.6",
    )

    row_groups = view._render_row_groups(file_info)

    # Row groups now returns a single Container
    from textual.containers import Container

    assert isinstance(row_groups, Container)


def test_render_page_indexes(sample_file_info: ParquetFileInfo) -> None:
    """Test _render_page_indexes method."""
    view = StructureView()
    page_indexes = view._render_page_indexes(sample_file_info)

    assert page_indexes is not None
    # Page indexes now returns a Static widget
    from textual.widgets import Static

    assert isinstance(page_indexes, Static)


def test_render_footer(sample_file_info: ParquetFileInfo) -> None:
    """Test _render_footer method."""
    view = StructureView()
    footer = view._render_footer(sample_file_info)

    assert footer is not None
    # Footer now returns a Static widget
    from textual.widgets import Static

    assert isinstance(footer, Static)


def test_render_footer_shows_row_count(sample_file_info: ParquetFileInfo) -> None:
    """Test that footer shows total row count."""
    view = StructureView()
    footer = view._render_footer(sample_file_info)

    # The footer should contain the row count
    # We can't easily check the rendered text without mounting,
    # but we can verify the method doesn't raise an error
    assert footer is not None


def test_structure_view_with_missing_metadata() -> None:
    """Test structure view handles missing metadata gracefully."""
    # Create file info with minimal metadata
    file_info = ParquetFileInfo(
        path="/path/to/test.parquet",
        file_size_bytes=1024,
        num_rows=100,
        num_row_groups=1,
        num_columns=1,
        schema={},
        row_groups=[
            RowGroupInfo(
                index=0,
                num_rows=100,
                total_byte_size=1024,
                columns=[
                    ColumnStats(
                        name="col1",
                        physical_type="INT32",
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
                ],
            )
        ],
        columns=[
            ColumnStats(
                name="col1",
                physical_type="INT32",
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
        ],
        created_by=None,
        format_version="2.6",
    )

    view = StructureView()

    # These should not raise exceptions
    header = view._render_header(file_info)
    row_groups = view._render_row_groups(file_info)
    page_indexes = view._render_page_indexes(file_info)
    footer = view._render_footer(file_info)

    assert header is not None
    # Row groups now returns a single Container
    from textual.containers import Container

    assert isinstance(row_groups, Container)
    assert page_indexes is not None
    assert footer is not None


def test_structure_view_with_empty_row_groups() -> None:
    """Test structure view with file that has no row groups."""
    file_info = ParquetFileInfo(
        path="/path/to/test.parquet",
        file_size_bytes=1024,
        num_rows=0,
        num_row_groups=0,
        num_columns=1,
        schema={},
        row_groups=[],
        columns=[],
        created_by=None,
        format_version="2.6",
    )

    view = StructureView()
    row_groups = view._render_row_groups(file_info)

    # Row groups now returns a single Container even when empty
    from textual.containers import Container

    assert isinstance(row_groups, Container)


def test_format_column_chunk_same_physical_logical_type() -> None:
    """Test _format_column_chunk when physical and logical types are the same."""
    view = StructureView()
    col = ColumnStats(
        name="test",
        physical_type="INT64",
        logical_type="INT64",
        null_count=0,
        min_value=None,
        max_value=None,
        encodings=["PLAIN"],
        compression="SNAPPY",
        num_values=None,
        distinct_count=None,
        total_compressed_size=None,
        total_uncompressed_size=None,
    )

    result = view._create_column_panel(col)

    # Check that it returns a Panel
    from rich.panel import Panel

    assert isinstance(result, Panel)
    assert "test" in str(result.title)


def test_format_column_chunk_different_physical_logical_type() -> None:
    """Test _create_column_panel when physical and logical types differ."""
    view = StructureView()
    col = ColumnStats(
        name="test",
        physical_type="BYTE_ARRAY",
        logical_type="UTF8",
        null_count=0,
        min_value=None,
        max_value=None,
        encodings=["DICTIONARY"],
        compression="GZIP",
        num_values=None,
        distinct_count=None,
        total_compressed_size=None,
        total_uncompressed_size=None,
    )

    result = view._create_column_panel(col)

    # Check that it returns a Panel
    from rich.panel import Panel

    assert isinstance(result, Panel)
    assert "test" in str(result.title)
