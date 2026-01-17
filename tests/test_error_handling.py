"""Tests for error handling and user feedback."""

from __future__ import annotations

import pytest

from tablesleuth.config import AppConfig, CatalogConfig, GizmoConfig
from tablesleuth.models import TableHandle
from tablesleuth.services.formats.iceberg import IcebergAdapter
from tablesleuth.tui.app import TableSleuthApp
from tablesleuth.tui.widgets import LoadingIndicator, Notification


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


def test_notification_widget_initialization() -> None:
    """Test notification widget can be initialized."""
    notification = Notification()
    assert notification is not None


def test_loading_indicator_initialization() -> None:
    """Test loading indicator can be initialized."""
    loading = LoadingIndicator()
    assert loading is not None


def test_app_has_notification_widget(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app includes notification widget."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify app has compose method that would include notification
    assert hasattr(app, "compose")


def test_app_has_loading_indicator(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that app includes loading indicator."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify app has loading methods
    assert hasattr(app, "_show_loading")
    assert hasattr(app, "_clear_loading")


def test_show_loading_unmounted(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test show_loading handles unmounted state."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Should not raise error
    app._show_loading("Test message")


def test_clear_loading_unmounted(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test clear_loading handles unmounted state."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Should not raise error
    app._clear_loading()


def test_show_error_unmounted(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test show_error handles unmounted state."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Should not raise error
    app._show_error("Test error message")


def test_error_handling_methods_exist(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that error handling methods exist."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify error handling methods
    assert hasattr(app, "_show_error")
    assert callable(app._show_error)


def test_loading_indicator_methods_exist(
    table_handle: TableHandle,
    adapter: IcebergAdapter,
    app_config: AppConfig,
) -> None:
    """Test that loading indicator methods exist."""
    app = TableSleuthApp(
        table_handle=table_handle,
        adapter=adapter,
        config=app_config,
    )

    # Verify loading methods
    assert hasattr(app, "_show_loading")
    assert hasattr(app, "_clear_loading")
    assert callable(app._show_loading)
    assert callable(app._clear_loading)


def test_notification_widget_has_methods() -> None:
    """Test notification widget has required methods."""
    notification = Notification()

    # Verify methods exist
    assert hasattr(notification, "show")
    assert hasattr(notification, "dismiss")
    assert hasattr(notification, "info")
    assert hasattr(notification, "success")
    assert hasattr(notification, "warning")
    assert hasattr(notification, "error")


def test_loading_indicator_has_methods() -> None:
    """Test loading indicator has required methods."""
    loading = LoadingIndicator()

    # Verify methods exist
    assert hasattr(loading, "show")
    assert hasattr(loading, "hide")
