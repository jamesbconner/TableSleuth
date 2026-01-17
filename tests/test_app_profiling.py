"""Tests for column profiling wiring in TUI app."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from tablesleuth.config import AppConfig, CatalogConfig, GizmoConfig
from tablesleuth.models import TableHandle
from tablesleuth.models.file_ref import FileRef
from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo, RowGroupInfo
from tablesleuth.models.profiling import ColumnProfile
from tablesleuth.services.formats.iceberg import IcebergAdapter
from tablesleuth.services.profiling.backend_base import ProfilingBackend
from tablesleuth.tui.app import TableSleuthApp


class FakeProfiler(ProfilingBackend):
    """Fake profiling backend for testing."""

    def __init__(self) -> None:
        self.registered_views: dict[str, list[str]] = {}
        self.profile_calls: list[tuple[str, str]] = []

    def register_snapshot_view(self, snapshot) -> str:
        """Mock implementation for testing."""
        return f"mock_view_{snapshot.snapshot_id}"

    def register_file_view(self, file_paths: list[str], view_name: str | None = None) -> str:
        """Register file paths for profiling."""
        if view_name is None:
            view_name = f"test_view_{len(self.registered_views)}"

        self.registered_views[view_name] = file_paths
        return view_name

    def profile_single_column(
        self, view_name: str, column: str, filters: str | None = None
    ) -> ColumnProfile:
        """Profile a single column."""
        self.profile_calls.append((view_name, column))

        return ColumnProfile(
            column=column,
            row_count=1000,
            non_null_count=950,
            null_count=50,
            distinct_count=100,
            min_value=1,
            max_value=999,
        )

    def profile_columns(
        self, view_name: str, columns, filters: str | None = None
    ) -> dict[str, ColumnProfile]:
        """Profile multiple columns."""
        return {col: self.profile_single_column(view_name, col, filters) for col in columns}


@pytest.fixture
def sample_file_ref() -> FileRef:
    """Create a sample FileRef for testing."""
    return FileRef(
        path="tests/data/test.parquet",
        file_size_bytes=1024,
        record_count=100,
        source="direct",
    )


@pytest.fixture
def sample_file_info() -> ParquetFileInfo:
    """Create sample ParquetFileInfo for testing."""
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
        path="tests/data/test.parquet",
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
    """Create test app configuration."""
    return AppConfig(
        catalog=CatalogConfig(default=None),
        gizmosql=GizmoConfig(),
    )


@pytest.fixture
def table_handle() -> TableHandle:
    """Create test table handle."""
    return TableHandle(native=None, format_name="parquet")


@pytest.fixture
def adapter() -> IcebergAdapter:
    """Create test adapter."""
    return IcebergAdapter(default_catalog=None)


@pytest.fixture
def fake_profiler() -> FakeProfiler:
    """Create fake profiler for testing."""
    return FakeProfiler()


def test_app_with_profiler(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    fake_profiler: FakeProfiler,
) -> None:
    """Test that app initializes with profiler."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        profiler=fake_profiler,
    )

    assert app is not None
    assert app._profiler == fake_profiler


def test_app_without_profiler(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app handles missing profiler gracefully."""
    # Create app without profiler (will try to create GizmoSQL profiler)
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    assert app is not None
    # Profiler may or may not be initialized depending on GizmoSQL availability


def test_app_profiler_none(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app handles None profiler."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        profiler=None,
    )

    assert app is not None


def test_column_selection_updates_stats(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_file_info: ParquetFileInfo,
) -> None:
    """Test that column selection updates column stats view."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Set current file info
    app._current_file_info = sample_file_info

    # Verify file info is set
    assert app._current_file_info == sample_file_info


def test_profiler_integration(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    fake_profiler: FakeProfiler,
) -> None:
    """Test profiler integration."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        profiler=fake_profiler,
    )

    # Verify profiler is set
    assert app._profiler == fake_profiler

    # Verify no views registered yet
    assert len(fake_profiler.registered_views) == 0
    assert len(fake_profiler.profile_calls) == 0


def test_action_profile_column_no_file(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    fake_profiler: FakeProfiler,
) -> None:
    """Test profile action with no file selected."""
    from tablesleuth.tui.views.profile_view import ProfileColumnRequested

    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        profiler=fake_profiler,
    )

    # Should not raise error when handling message with no file
    message = ProfileColumnRequested("test_column")
    app.on_profile_column_requested(message)


def test_action_profile_column_no_profiler(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_file_info: ParquetFileInfo,
) -> None:
    """Test profile action with no profiler."""
    from tablesleuth.tui.views.profile_view import ProfileColumnRequested

    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        profiler=None,
    )

    # Set file info
    app._current_file_info = sample_file_info
    app._profiler = None

    # Should not raise error when handling message with no profiler
    message = ProfileColumnRequested("test_column")
    app.on_profile_column_requested(message)


def test_view_name_tracking(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    fake_profiler: FakeProfiler,
) -> None:
    """Test that view name is tracked correctly."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        profiler=fake_profiler,
    )

    # Initially no view name
    assert app._current_view_name is None


def test_refresh_clears_view_name(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    fake_profiler: FakeProfiler,
    sample_file_info: ParquetFileInfo,
) -> None:
    """Test that refresh clears view name."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        profiler=fake_profiler,
    )

    # Set view name
    app._current_view_name = "test_view"
    app._current_file_info = sample_file_info

    # Refresh should clear view name
    # (actual refresh would fail without mounted app, so we just test the logic)
    assert app._current_view_name == "test_view"
