"""Tests for file selection and inspection wiring in TUI app."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from tablesleuth.config import AppConfig, CatalogConfig, GizmoConfig
from tablesleuth.models import TableHandle
from tablesleuth.models.file_ref import FileRef
from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo, RowGroupInfo
from tablesleuth.services.formats.iceberg import IcebergAdapter
from tablesleuth.tui.app import TableSleuthApp


@pytest.fixture
def sample_file_ref() -> FileRef:
    """Create a sample FileRef for testing.

    Returns:
        FileRef with test data
    """
    return FileRef(
        path="tests/data/nested_test.parquet",
        file_size_bytes=1024,
        record_count=100,
        source="direct",
    )


@pytest.fixture
def sample_file_info() -> ParquetFileInfo:
    """Create sample ParquetFileInfo for testing.

    Returns:
        ParquetFileInfo with test data
    """
    columns = [
        ColumnStats(
            name="id",
            physical_type="INT64",
            logical_type="INT64",
            null_count=0,
            min_value=1,
            max_value=100,
            encodings=["PLAIN"],
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
            encodings=["PLAIN", "RLE"],
            compression="SNAPPY",
            num_values=None,
            distinct_count=None,
            total_compressed_size=None,
            total_uncompressed_size=None,
        ),
    ]

    row_groups = [
        RowGroupInfo(
            index=0,
            num_rows=100,
            total_byte_size=512,
            columns=columns,
        )
    ]

    return ParquetFileInfo(
        path="tests/data/nested_test.parquet",
        file_size_bytes=1024,
        num_rows=100,
        num_row_groups=1,
        num_columns=2,
        schema={"id": {"type": "int64", "nullable": False}},
        row_groups=row_groups,
        columns=columns,
        created_by="test",
        format_version="2.0",
    )


@pytest.fixture
def app_config() -> AppConfig:
    """Create test app configuration.

    Returns:
        AppConfig for testing
    """
    return AppConfig(
        catalog=CatalogConfig(default=None),
        gizmosql=GizmoConfig(),
    )


@pytest.fixture
def table_handle() -> TableHandle:
    """Create test table handle.

    Returns:
        TableHandle for testing
    """
    return TableHandle(native=None, format_name="parquet")


@pytest.fixture
def adapter() -> IcebergAdapter:
    """Create test adapter.

    Returns:
        IcebergAdapter for testing
    """
    return IcebergAdapter(default_catalog=None)


def test_app_initialization(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_file_ref: FileRef,
) -> None:
    """Test that app initializes with files."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=[sample_file_ref],
    )

    assert app is not None
    assert len(app._files) == 1
    assert app._files[0] == sample_file_ref
    assert app._inspector is not None
    assert app._current_file_info is None


def test_app_initialization_no_files(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app initializes without files."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    assert app is not None
    assert len(app._files) == 0
    assert app._inspector is not None


def test_update_views(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_file_info: ParquetFileInfo,
) -> None:
    """Test that _update_views updates internal state."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Store file info
    app._current_file_info = sample_file_info

    assert app._current_file_info == sample_file_info


def test_show_loading(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test loading indicator."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Should not raise any errors
    app._show_loading("Testing...")
    app._clear_loading()


def test_show_error(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test error display."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Should not raise any errors
    app._show_error("Test error message")


def test_inspector_integration(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that ParquetInspector is properly integrated."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify inspector is available
    assert app._inspector is not None

    # Verify inspector has expected methods
    assert hasattr(app._inspector, "inspect_file")
    assert hasattr(app._inspector, "get_schema")
    assert hasattr(app._inspector, "get_row_groups")
    assert hasattr(app._inspector, "get_column_stats")


def test_app_with_real_test_file(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_parquet_file: Path,
) -> None:
    """Test app with real test Parquet file."""
    test_file = sample_parquet_file

    file_ref = FileRef(
        path=str(test_file),
        file_size_bytes=test_file.stat().st_size,
        record_count=None,
        source="direct",
    )

    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=[file_ref],
    )

    assert app is not None
    assert len(app._files) == 1

    # Test that inspector can actually inspect the file
    file_info = app._inspector.inspect_file(str(test_file))
    assert file_info is not None
    assert file_info.num_rows > 0
    assert file_info.num_columns > 0
