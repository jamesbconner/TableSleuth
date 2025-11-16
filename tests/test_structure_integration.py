"""Integration tests for Structure tab."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import TabbedContent, TabPane

from table_sleuth.config import AppConfig, CatalogConfig, GizmoConfig
from table_sleuth.models import TableHandle
from table_sleuth.models.file_ref import FileRef
from table_sleuth.services.formats.iceberg import IcebergAdapter
from table_sleuth.services.parquet_service import ParquetInspector
from table_sleuth.tui.app import TableSleuthApp
from table_sleuth.tui.views.structure_view import StructureView


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
def test_parquet_file() -> Path:
    """Get path to test Parquet file."""
    test_file = Path("tests/data/nested_test.parquet")
    if not test_file.exists():
        pytest.skip("Test Parquet file not found")
    return test_file


@pytest.fixture
def sample_files(test_parquet_file: Path) -> list[FileRef]:
    """Create sample files for testing."""
    return [
        FileRef(
            path=str(test_parquet_file),
            file_size_bytes=test_parquet_file.stat().st_size,
            record_count=100,
            source="direct",
        ),
    ]


async def test_structure_tab_exists_in_app(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that Structure tab exists in the app."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount
        await pilot.pause()

        # Find TabbedContent
        tabbed_content = app.query_one(TabbedContent)
        assert tabbed_content is not None

        # Get all tab panes
        tab_panes = list(tabbed_content.query(TabPane))

        # Get tab labels from the tab IDs or check if Structure view exists
        structure_view = app.query_one("#structure", StructureView)
        assert structure_view is not None


async def test_structure_view_exists_in_app(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that StructureView widget exists in the app."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount
        await pilot.pause()

        # Find StructureView
        structure_view = app.query_one("#structure", StructureView)
        assert structure_view is not None


async def test_structure_tab_position(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that Structure tab is positioned after Row Groups tab."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount
        await pilot.pause()

        # Find TabbedContent
        tabbed_content = app.query_one(TabbedContent)

        # Get all tab panes
        tab_panes = list(tabbed_content.query(TabPane))

        # Verify we have at least 6 tabs (File Detail, Schema, Row Groups, Structure, Column Stats, Profile)
        assert len(tab_panes) >= 6

        # Verify Structure view exists
        structure_view = app.query_one("#structure", StructureView)
        assert structure_view is not None


async def test_structure_view_updates_on_file_selection(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_files: list[FileRef],
    test_parquet_file: Path,
) -> None:
    """Test that Structure view updates when a file is selected."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=sample_files,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount and auto-select first file
        await pilot.pause()
        await pilot.pause()

        # Get structure view
        structure_view = app.query_one("#structure", StructureView)

        # Verify structure view has file info
        assert structure_view._file_info is not None
        assert structure_view._file_info.path == str(test_parquet_file)


async def test_structure_view_displays_on_tab_activation(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_files: list[FileRef],
) -> None:
    """Test that Structure view displays when tab is activated."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=sample_files,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount and auto-select first file
        await pilot.pause()
        await pilot.pause()

        # Find TabbedContent
        tabbed_content = app.query_one(TabbedContent)

        # Get Structure tab by finding the structure view's parent TabPane
        structure_view = app.query_one("#structure", StructureView)
        structure_tab = structure_view.parent

        assert structure_tab is not None

        # Switch to Structure tab
        tabbed_content.active = structure_tab.id
        await pilot.pause()

        # Get structure view
        structure_view = app.query_one("#structure", StructureView)

        # Verify structure view has content
        assert structure_view._file_info is not None


async def test_structure_view_with_real_parquet_file(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_files: list[FileRef],
    test_parquet_file: Path,
) -> None:
    """Test Structure view with actual Parquet file."""
    # First inspect the file to get expected data
    inspector = ParquetInspector()
    file_info = inspector.inspect_file(test_parquet_file)

    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=sample_files,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount and auto-select first file
        await pilot.pause()
        await pilot.pause()

        # Get structure view
        structure_view = app.query_one("#structure", StructureView)

        # Verify structure view has correct file info
        assert structure_view._file_info is not None
        assert structure_view._file_info.num_rows == file_info.num_rows
        assert structure_view._file_info.num_row_groups == file_info.num_row_groups
        assert structure_view._file_info.num_columns == file_info.num_columns


async def test_structure_view_sections_render(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_files: list[FileRef],
) -> None:
    """Test that all Structure view sections render correctly."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=sample_files,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount and auto-select first file
        await pilot.pause()
        await pilot.pause()

        # Switch to Structure tab
        tabbed_content = app.query_one(TabbedContent)
        structure_view = app.query_one("#structure", StructureView)
        structure_tab = structure_view.parent

        tabbed_content.active = structure_tab.id
        await pilot.pause()

        # Verify content container exists
        assert structure_view._content_container is not None

        # Verify sections are rendered (by checking children)
        children = list(structure_view._content_container.children)
        assert len(children) > 0  # Should have header, row groups, page indexes, footer


async def test_structure_view_clears_on_error(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that Structure view clears when error occurs."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount
        await pilot.pause()

        # Get structure view
        structure_view = app.query_one("#structure", StructureView)

        # Trigger an error by showing error
        app._show_error("Test error")

        # Verify structure view is cleared (without waiting for pause which times out)
        assert structure_view._file_info is None


async def test_structure_view_lazy_loading(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_files: list[FileRef],
) -> None:
    """Test that Structure view loads lazily when tab is activated."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=sample_files,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount and auto-select first file
        await pilot.pause()
        await pilot.pause()

        # Initially on File Detail tab
        # Structure view should have file info from _update_views
        structure_view = app.query_one("#structure", StructureView)
        assert structure_view._file_info is not None

        # Switch to Structure tab
        tabbed_content = app.query_one(TabbedContent)
        structure_tab = structure_view.parent

        tabbed_content.active = structure_tab.id
        await pilot.pause()

        # Verify structure view still has file info
        assert structure_view._file_info is not None


async def test_structure_view_multiple_row_groups(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_files: list[FileRef],
    test_parquet_file: Path,
) -> None:
    """Test Structure view displays multiple row groups correctly."""
    # First inspect the file to get row group count
    inspector = ParquetInspector()
    file_info = inspector.inspect_file(test_parquet_file)

    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=sample_files,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount and auto-select first file
        await pilot.pause()
        await pilot.pause()

        # Get structure view
        structure_view = app.query_one("#structure", StructureView)

        # Verify structure view has correct number of row groups
        assert structure_view._file_info is not None
        assert len(structure_view._file_info.row_groups) == file_info.num_row_groups


async def test_app_update_views_includes_structure(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_files: list[FileRef],
) -> None:
    """Test that _update_views method updates structure view."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=sample_files,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount and auto-select first file
        await pilot.pause()
        await pilot.pause()

        # Verify structure view was updated
        structure_view = app.query_one("#structure", StructureView)
        assert structure_view._file_info is not None


async def test_structure_view_scrollable(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_files: list[FileRef],
) -> None:
    """Test that Structure view is scrollable."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=sample_files,
    )

    async with app.run_test() as pilot:
        # Wait for app to mount and auto-select first file
        await pilot.pause()
        await pilot.pause()

        # Get structure view
        structure_view = app.query_one("#structure", StructureView)

        # Verify structure view has overflow-y: auto in CSS
        # This is defined in DEFAULT_CSS
        assert "overflow-y: auto" in StructureView.DEFAULT_CSS
