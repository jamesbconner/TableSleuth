"""Tests for ParquetInspector service."""

from __future__ import annotations

from pathlib import Path

import pytest

from table_sleuth.services.parquet_service import ParquetInspector


@pytest.fixture
def inspector() -> ParquetInspector:
    """Create a ParquetInspector instance."""
    return ParquetInspector()


@pytest.fixture
def test_parquet_file() -> Path:
    """Get path to test Parquet file."""
    test_file = Path("tests/data/nested_test.parquet")
    if not test_file.exists():
        pytest.skip("Test Parquet file not found")
    return test_file


def test_inspector_initialization(inspector: ParquetInspector) -> None:
    """Test that ParquetInspector can be initialized."""
    assert inspector is not None


def test_inspect_file_returns_file_info(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that inspect_file returns ParquetFileInfo."""
    file_info = inspector.inspect_file(test_parquet_file)

    assert file_info is not None
    assert file_info.path == str(test_parquet_file)
    assert file_info.num_rows > 0
    assert file_info.num_columns > 0
    assert file_info.num_row_groups > 0


def test_inspect_file_extracts_schema(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that inspect_file extracts schema information."""
    file_info = inspector.inspect_file(test_parquet_file)

    assert file_info.schema is not None
    assert isinstance(file_info.schema, dict)
    assert len(file_info.schema) > 0


def test_inspect_file_extracts_row_groups(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that inspect_file extracts row group information."""
    file_info = inspector.inspect_file(test_parquet_file)

    assert file_info.row_groups is not None
    assert isinstance(file_info.row_groups, list)
    assert len(file_info.row_groups) == file_info.num_row_groups

    # Verify row group structure
    for rg in file_info.row_groups:
        assert rg.index >= 0
        assert rg.num_rows > 0
        assert rg.total_byte_size > 0
        assert len(rg.columns) > 0


def test_inspect_file_extracts_columns(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that inspect_file extracts column information."""
    file_info = inspector.inspect_file(test_parquet_file)

    assert file_info.columns is not None
    assert isinstance(file_info.columns, list)
    assert len(file_info.columns) == file_info.num_columns

    # Verify column structure
    for col in file_info.columns:
        assert col.name
        assert col.physical_type
        assert isinstance(col.encodings, list)
        assert col.compression


def test_inspect_file_handles_missing_statistics(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that inspect_file handles missing statistics gracefully."""
    file_info = inspector.inspect_file(test_parquet_file)

    # Some columns may not have statistics
    # Verify we handle None values gracefully
    for col in file_info.columns:
        # These can be None
        assert col.null_count is None or isinstance(col.null_count, int)
        # min/max can be None for some types
        # Just verify no exceptions are raised


def test_inspect_file_nonexistent_file(inspector: ParquetInspector) -> None:
    """Test that inspect_file raises FileNotFoundError for nonexistent file."""
    with pytest.raises(FileNotFoundError):
        inspector.inspect_file("nonexistent.parquet")


def test_inspect_file_invalid_file(inspector: ParquetInspector, tmp_path: Path) -> None:
    """Test that inspect_file raises ValueError for invalid Parquet file."""
    # Create a non-Parquet file
    invalid_file = tmp_path / "invalid.parquet"
    invalid_file.write_text("not a parquet file")

    with pytest.raises(ValueError):
        inspector.inspect_file(invalid_file)


def test_get_schema(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test get_schema method."""
    schema = inspector.get_schema(test_parquet_file)

    assert schema is not None
    assert isinstance(schema, dict)
    assert len(schema) > 0

    # Verify schema structure
    for col_name, col_info in schema.items():
        assert isinstance(col_name, str)
        assert isinstance(col_info, dict)


def test_get_row_groups(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test get_row_groups method."""
    row_groups = inspector.get_row_groups(test_parquet_file)

    assert row_groups is not None
    assert isinstance(row_groups, list)
    assert len(row_groups) > 0

    # Verify row group structure
    for i, rg in enumerate(row_groups):
        assert rg.index == i
        assert rg.num_rows > 0
        assert rg.total_byte_size > 0
        assert len(rg.columns) > 0


def test_get_column_stats(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test get_column_stats method."""
    # First get schema to find a column name
    file_info = inspector.inspect_file(test_parquet_file)
    column_name = file_info.columns[0].name

    # Get stats for that column
    col_stats = inspector.get_column_stats(test_parquet_file, column_name)

    assert col_stats is not None
    assert col_stats.name == column_name
    assert col_stats.physical_type
    assert isinstance(col_stats.encodings, list)
    assert col_stats.compression


def test_get_column_stats_invalid_column(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test get_column_stats with invalid column name."""
    with pytest.raises(ValueError, match="not found"):
        inspector.get_column_stats(test_parquet_file, "nonexistent_column")


def test_inspect_file_with_path_object(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that inspect_file works with Path objects."""
    file_info = inspector.inspect_file(test_parquet_file)
    assert file_info is not None


def test_inspect_file_with_string_path(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that inspect_file works with string paths."""
    file_info = inspector.inspect_file(str(test_parquet_file))
    assert file_info is not None


def test_inspect_file_metadata_fields(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that inspect_file extracts all metadata fields."""
    file_info = inspector.inspect_file(test_parquet_file)

    # Verify all required fields are present
    assert hasattr(file_info, "path")
    assert hasattr(file_info, "file_size_bytes")
    assert hasattr(file_info, "num_rows")
    assert hasattr(file_info, "num_row_groups")
    assert hasattr(file_info, "num_columns")
    assert hasattr(file_info, "schema")
    assert hasattr(file_info, "row_groups")
    assert hasattr(file_info, "columns")
    assert hasattr(file_info, "created_by")
    assert hasattr(file_info, "format_version")


def test_column_stats_structure(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that column stats have correct structure."""
    file_info = inspector.inspect_file(test_parquet_file)

    for col in file_info.columns:
        # Required fields
        assert hasattr(col, "name")
        assert hasattr(col, "physical_type")
        assert hasattr(col, "logical_type")
        assert hasattr(col, "null_count")
        assert hasattr(col, "min_value")
        assert hasattr(col, "max_value")
        assert hasattr(col, "encodings")
        assert hasattr(col, "compression")


def test_row_group_stats_structure(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that row group stats have correct structure."""
    file_info = inspector.inspect_file(test_parquet_file)

    for rg in file_info.row_groups:
        # Required fields
        assert hasattr(rg, "index")
        assert hasattr(rg, "num_rows")
        assert hasattr(rg, "total_byte_size")
        assert hasattr(rg, "columns")

        # Verify columns in row group
        assert len(rg.columns) == file_info.num_columns


def test_inspect_file_file_size(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that file size is correctly reported."""
    file_info = inspector.inspect_file(test_parquet_file)

    # File size should match actual file size
    actual_size = test_parquet_file.stat().st_size
    assert file_info.file_size_bytes == actual_size


def test_inspect_file_format_version(
    inspector: ParquetInspector,
    test_parquet_file: Path,
) -> None:
    """Test that format version is extracted."""
    file_info = inspector.inspect_file(test_parquet_file)

    assert file_info.format_version is not None
    assert isinstance(file_info.format_version, str)
