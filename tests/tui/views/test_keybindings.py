"""Tests for keybindings and navigation."""

from __future__ import annotations

import pytest

from tablesleuth.config import AppConfig, CatalogConfig, GizmoConfig
from tablesleuth.models import TableHandle
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


def test_app_has_keybindings(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app has keybindings defined."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    assert hasattr(app, "BINDINGS")
    assert len(app.BINDINGS) > 0


def test_quit_keybinding(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test quit keybinding is defined."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Extract binding keys
    binding_keys = [b[0] for b in app.BINDINGS]

    # Verify quit binding
    assert "q" in binding_keys


def test_refresh_keybinding(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test refresh keybinding is defined."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Extract binding keys
    binding_keys = [b[0] for b in app.BINDINGS]

    # Verify refresh binding
    assert "r" in binding_keys


def test_profile_keybinding(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test profile keybinding is defined."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Extract binding keys
    binding_keys = [b[0] for b in app.BINDINGS]

    # Note: 'p' keybinding removed - profiling now done via ProfileView column selection


def test_filter_keybinding(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test filter keybinding is defined."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Extract binding keys
    binding_keys = [b[0] for b in app.BINDINGS]

    # Verify filter binding
    assert "f" in binding_keys


def test_tab_keybinding(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test tab keybinding is defined."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Extract binding keys
    binding_keys = [b[0] for b in app.BINDINGS]

    # Verify tab binding
    assert "tab" in binding_keys


def test_escape_keybinding(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test escape keybinding is defined."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Extract binding keys
    binding_keys = [b[0] for b in app.BINDINGS]

    # Verify escape binding
    assert "escape" in binding_keys


def test_action_quit_exists(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test quit action exists."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    assert hasattr(app, "action_quit")


def test_action_refresh_exists(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test refresh action exists."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    assert hasattr(app, "action_refresh")
    assert callable(app.action_refresh)


def test_action_profile_column_exists(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test profile column message handler exists."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Profile action replaced with message handler
    assert hasattr(app, "on_profile_column_requested")
    assert callable(app.on_profile_column_requested)


def test_action_focus_filter_exists(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test focus filter action exists."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    assert hasattr(app, "action_focus_filter")
    assert callable(app.action_focus_filter)


def test_action_dismiss_notification_exists(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test dismiss notification action exists."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    assert hasattr(app, "action_dismiss_notification")
    assert callable(app.action_dismiss_notification)


def test_action_focus_next_exists(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test focus next action exists (inherited from Textual)."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # This is a built-in Textual action
    assert hasattr(app, "action_focus_next")


def test_action_focus_previous_exists(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test focus previous action exists (inherited from Textual)."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # This is a built-in Textual action
    assert hasattr(app, "action_focus_previous")


def test_all_required_keybindings_present(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that all required keybindings are present."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Extract binding keys
    binding_keys = [b[0] for b in app.BINDINGS]

    # Required keybindings from task
    # Note: 'p' removed - profiling now done via ProfileView column selection
    required_keys = ["q", "r", "f", "tab"]

    for key in required_keys:
        assert key in binding_keys, f"Required keybinding '{key}' not found"


def test_keybinding_descriptions(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that keybindings have descriptions."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # All bindings should have descriptions
    for binding in app.BINDINGS:
        assert len(binding) >= 3, "Binding should have key, action, and description"
        assert binding[2], "Binding description should not be empty"


def test_action_dismiss_notification_unmounted(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test dismiss notification action handles unmounted state."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Should not raise error
    app.action_dismiss_notification()


def test_action_focus_filter_unmounted(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test focus filter action handles unmounted state."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Should not raise error
    app.action_focus_filter()
