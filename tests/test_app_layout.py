"""Tests for TUI application layout and structure."""

from __future__ import annotations

import pytest

from tablesleuth.config import AppConfig, CatalogConfig, GizmoConfig
from tablesleuth.models import TableHandle
from tablesleuth.models.file_ref import FileRef
from tablesleuth.services.formats.iceberg import IcebergAdapter
from tablesleuth.tui.app import TableSleuthApp


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
def sample_files() -> list[FileRef]:
    """Create sample files for testing."""
    return [
        FileRef(
            path="tests/data/file1.parquet",
            file_size_bytes=1024,
            record_count=100,
            source="direct",
        ),
        FileRef(
            path="tests/data/file2.parquet",
            file_size_bytes=2048,
            record_count=200,
            source="direct",
        ),
    ]


def test_app_has_title(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app has a title."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    assert app.TITLE == "Table Sleuth - Parquet Analysis"
    assert app.SUB_TITLE == ""


def test_app_has_keybindings(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app has required keybindings."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Check that bindings are defined
    assert len(app.BINDINGS) >= 3

    # Extract binding keys
    binding_keys = [b[0] for b in app.BINDINGS]

    # Verify required bindings
    assert "q" in binding_keys  # Quit
    assert "r" in binding_keys  # Refresh
    # Note: 'p' keybinding removed - profiling now done via ProfileView column selection


def test_app_with_files(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
    sample_files: list[FileRef],
) -> None:
    """Test that app initializes with files."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
        files=sample_files,
    )

    assert len(app._files) == 2
    assert app._files[0].path == "tests/data/file1.parquet"
    assert app._files[1].path == "tests/data/file2.parquet"


def test_app_compose_method(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app has compose method."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify compose method exists
    assert hasattr(app, "compose")
    assert callable(app.compose)


def test_app_has_required_actions(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app has required action methods."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify action methods exist
    assert hasattr(app, "action_quit")
    assert hasattr(app, "action_refresh")
    # Note: action_profile_column removed - profiling now handled via ProfileColumnRequested message
    assert hasattr(app, "action_focus_filter")
    assert hasattr(app, "action_focus_next")


def test_app_has_event_handlers(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app has required event handlers."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify event handlers exist
    assert hasattr(app, "on_mount")
    assert hasattr(app, "on_data_table_row_selected")


def test_app_has_internal_methods(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app has required internal methods."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify internal methods exist
    assert hasattr(app, "_inspect_file")
    assert hasattr(app, "_update_views")
    assert hasattr(app, "_show_loading")
    assert hasattr(app, "_clear_loading")
    assert hasattr(app, "_show_error")
    assert hasattr(app, "_on_column_selected")
    assert hasattr(app, "_profile_column")


def test_app_css_defined(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app has CSS defined."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify CSS is defined
    assert hasattr(app, "CSS")
    assert isinstance(app.CSS, str)
    assert len(app.CSS) > 0

    # Verify key CSS selectors are present
    assert "#left-panel" in app.CSS
    assert "#right-panel" in app.CSS


def test_app_state_initialization(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app state is properly initialized."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify initial state
    assert app._current_file_info is None
    assert app._current_view_name is None
    assert app._inspector is not None
    assert app._files == []


def test_action_focus_filter(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test focus filter action."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Should not raise error even when not mounted
    app.action_focus_filter()
