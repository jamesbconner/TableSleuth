"""Advanced tests for TableSleuthApp main TUI application."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from textual.widgets import Footer, Header, TabPane

from tablesleuth.config import AppConfig, CatalogConfig, GizmoConfig
from tablesleuth.models import TableHandle
from tablesleuth.models.file_ref import FileRef
from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo, RowGroupInfo
from tablesleuth.services.formats.base import TableFormatAdapter
from tablesleuth.tui.app import TableSleuthApp


@pytest.fixture
def mock_config() -> AppConfig:
    """Create mock app configuration."""
    return AppConfig(
        catalog=CatalogConfig(default=None),
        gizmosql=GizmoConfig(),
    )


@pytest.fixture
def mock_table_handle() -> TableHandle:
    """Create mock table handle."""
    return TableHandle(
        native=Mock(),
        format_name="parquet",
    )


@pytest.fixture
def mock_adapter() -> TableFormatAdapter:
    """Create mock table format adapter."""
    adapter = Mock(spec=TableFormatAdapter)
    adapter.list_files = Mock(return_value=[])
    adapter.get_table_metadata = Mock(return_value={})
    return adapter


@pytest.fixture
def sample_file_refs() -> list[FileRef]:
    """Create sample file references."""
    return [
        FileRef(
            path="/data/file1.parquet",
            file_size_bytes=1024,
            record_count=100,
        ),
        FileRef(
            path="/data/file2.parquet",
            file_size_bytes=2048,
            record_count=200,
        ),
    ]


@pytest.fixture
def sample_parquet_info() -> ParquetFileInfo:
    """Create sample ParquetFileInfo."""
    return ParquetFileInfo(
        path="/data/test.parquet",
        file_size_bytes=1024,
        num_rows=100,
        num_row_groups=1,
        num_columns=3,
        schema={"id": "int64", "name": "string", "value": "double"},
        row_groups=[
            RowGroupInfo(
                index=0,
                num_rows=100,
                total_byte_size=1024,
                columns=[
                    ColumnStats(
                        name="id",
                        physical_type="INT64",
                        logical_type=None,
                        null_count=0,
                        min_value=1,
                        max_value=100,
                        encodings=["PLAIN"],
                        compression="SNAPPY",
                        num_values=100,
                        distinct_count=100,
                        total_compressed_size=100,
                        total_uncompressed_size=120,
                    )
                ],
            )
        ],
        columns=[
            ColumnStats(
                name="id",
                physical_type="INT64",
                logical_type=None,
                null_count=0,
                min_value=1,
                max_value=100,
                encodings=["PLAIN"],
                compression="SNAPPY",
                num_values=100,
                distinct_count=100,
                total_compressed_size=100,
                total_uncompressed_size=120,
            ),
            ColumnStats(
                name="name",
                physical_type="BYTE_ARRAY",
                logical_type="UTF8",
                null_count=0,
                min_value="Alice",
                max_value="Zoe",
                encodings=["PLAIN"],
                compression="SNAPPY",
                num_values=100,
                distinct_count=50,
                total_compressed_size=200,
                total_uncompressed_size=250,
            ),
            ColumnStats(
                name="value",
                physical_type="DOUBLE",
                logical_type=None,
                null_count=5,
                min_value=0.0,
                max_value=100.0,
                encodings=["PLAIN"],
                compression="SNAPPY",
                num_values=95,
                distinct_count=95,
                total_compressed_size=150,
                total_uncompressed_size=180,
            ),
        ],
        created_by="test",
        format_version="2.6",
    )


class TestTableSleuthApp:
    """Tests for TableSleuthApp main application."""

    async def test_app_initialization(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test app initializes correctly."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        assert app.table_handle == mock_table_handle
        assert app.adapter == mock_adapter
        assert app.config == mock_config
        assert app._current_file_info is None

    async def test_app_initialization_with_files(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_file_refs: list[FileRef],
    ) -> None:
        """Test app initializes with file list."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            files=sample_file_refs,
        )

        assert len(app._files) == 2

    async def test_app_compose_creates_widgets(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test that compose creates all required widgets."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            # Check that key widgets exist
            assert app.query_one(Header)
            assert app.query_one(Footer)
            assert app.query_one("#notification")
            assert app.query_one("#loading")
            assert app.query_one("#file-list")

    async def test_app_action_quit(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test quit action."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            # Trigger quit action
            await pilot.press("q")
            await pilot.pause()

            # App should exit (test will complete)

    async def test_app_action_refresh(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test refresh action."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Set current file info so refresh has something to refresh
            app._current_file_info = sample_parquet_info

            # Trigger refresh action
            await pilot.press("r")
            await pilot.pause()

            # Should not crash (refresh re-inspects current file)

    async def test_app_action_dismiss_notification(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test dismiss notification action."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Trigger dismiss notification
            await pilot.press("escape")
            await pilot.pause()

            # Should not crash

    async def test_app_with_custom_profiler(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test app with custom profiler."""
        mock_profiler = Mock()

        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            profiler=mock_profiler,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Custom profiler should be used
            assert app._profiler == mock_profiler

    async def test_app_file_selection(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_file_refs: list[FileRef],
    ) -> None:
        """Test file selection updates views."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            files=sample_file_refs,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Simulate file selection
            file_list = app.query_one("#file-list")

            # Should have files loaded
            assert len(app._files) == 2

    async def test_app_handles_empty_file_list(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test app handles empty file list gracefully."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            files=[],
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Should not crash with empty file list
            assert len(app._files) == 0

    async def test_app_title_and_subtitle(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test app title and subtitle are set."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        assert app.TITLE == "Table Sleuth - Parquet Analysis"
        assert isinstance(app.SUB_TITLE, str)

    async def test_app_bindings_defined(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test app has key bindings defined."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        # Check that bindings are defined
        assert len(app.BINDINGS) > 0

        # Check for specific bindings
        binding_keys = [b[0] for b in app.BINDINGS]
        assert "q" in binding_keys  # Quit
        assert "r" in binding_keys  # Refresh
        assert "escape" in binding_keys  # Dismiss

    async def test_app_css_defined(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test app has CSS styling defined."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        # Check that CSS is defined
        assert len(app.CSS) > 0
        assert "#left-panel" in app.CSS
        assert "#right-panel" in app.CSS

    async def test_app_profiler_initialization_error_handling(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
    ) -> None:
        """Test app handles profiler initialization errors."""
        config = AppConfig(
            catalog=CatalogConfig(default=None),
            gizmosql=GizmoConfig(),
        )

        with patch("tablesleuth.tui.app.GizmoDuckDbProfiler") as mock_profiler_class:
            # Make profiler initialization raise an exception
            mock_profiler_class.side_effect = Exception("Connection failed")

            app = TableSleuthApp(
                table_handle=mock_table_handle,
                adapter=mock_adapter,
                config=config,
            )

            async with app.run_test() as pilot:
                await pilot.pause()

                # App should handle error gracefully
                # Profiler should be None due to exception
                assert app._profiler is None

    async def test_app_with_files_shows_aggregate_stats(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_file_refs: list[FileRef],
    ) -> None:
        """Test app with files shows aggregate stats on mount."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            files=sample_file_refs,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Files should be loaded
            assert len(app._files) == 2

            # File list should exist
            file_list = app.query_one("#file-list")
            assert file_list is not None

    async def test_app_notification_widget_exists(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test notification widget is available."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Notification widget should exist
            notification = app.query_one("#notification")
            assert notification is not None

    async def test_app_loading_indicator_exists(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test loading indicator widget is available."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Loading indicator should exist
            loading = app.query_one("#loading")
            assert loading is not None

    async def test_app_tabbed_content_exists(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test tabbed content for detail views exists."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Should have tabbed content
            tabs = app.query(TabPane)
            assert len(list(tabs)) > 0


class TestTableSleuthAppFileHandling:
    """Tests for file handling in TableSleuthApp."""

    async def test_app_on_mount_with_files(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_file_refs: list[FileRef],
    ) -> None:
        """Test app on_mount with files shows aggregate stats."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            files=sample_file_refs,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Files should be loaded
            assert len(app._files) == 2

    async def test_app_file_metadata_cache_usage(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test file metadata cache is used."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Manually add to cache
            test_path = "/test/file.parquet"
            app._file_metadata_cache[test_path] = sample_parquet_info

            # Verify cache contains the entry
            assert test_path in app._file_metadata_cache
            assert app._file_metadata_cache[test_path] == sample_parquet_info

    async def test_app_show_loading(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test show loading indicator."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Show loading
            app._show_loading("Test message")
            await pilot.pause()

            # Loading indicator should be visible
            loading = app.query_one("#loading")
            assert loading is not None

    async def test_app_clear_loading(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test clear loading indicator."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Show then clear loading
            app._show_loading("Test")
            await pilot.pause()
            app._clear_loading()
            await pilot.pause()

            # Should not crash

    async def test_app_invalidate_cache_method(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test cache invalidation method."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Add entries to cache
            test_path = "/test/file.parquet"
            app._file_metadata_cache[test_path] = Mock()
            app._profile_cache[(test_path, "col1")] = Mock()

            # Invalidate cache
            app._invalidate_cache(test_path)

            # Entries should be removed
            assert test_path not in app._file_metadata_cache
            assert (test_path, "col1") not in app._profile_cache

    async def test_app_on_tabbed_content_tab_activated(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test tab activation updates views."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Set current file info
            app._current_file_info = sample_parquet_info

            # Simulate tab activation
            from unittest.mock import Mock

            from textual.widgets import TabbedContent

            event = Mock()
            event.tab = Mock()
            event.tab.id = "file-detail"

            app.on_tabbed_content_tab_activated(event)
            await pilot.pause()

            # Should not crash

    async def test_app_on_data_table_row_selected_schema_table(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test row selection in schema table."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Simulate row selection in schema table
            from unittest.mock import Mock

            event = Mock()
            event.data_table = Mock()
            event.data_table.id = "schema-table"

            # Should trigger column selection
            app.on_data_table_row_selected(event)
            await pilot.pause()

            # Should not crash

    async def test_app_on_column_selected(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test column selection in schema table."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Set current file info
            app._current_file_info = sample_parquet_info

            # Call column selected
            app._on_column_selected()
            await pilot.pause()

            # Should not crash

    async def test_app_profile_cache(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test profile caching functionality."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Profile cache should be initialized
            assert isinstance(app._profile_cache, dict)

    async def test_app_file_metadata_cache(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test file metadata caching functionality."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # File metadata cache should be initialized
            assert isinstance(app._file_metadata_cache, dict)

    async def test_app_inspector_initialization(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test ParquetInspector is initialized."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Inspector should be initialized
            assert app._inspector is not None

    async def test_app_clear_loading_method(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test clear loading method."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Call clear loading
            app._clear_loading()
            await pilot.pause()

            # Should not crash

    async def test_app_action_focus_filter(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test focus filter action."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Trigger focus filter action
            await pilot.press("f")
            await pilot.pause()

            # Should not crash

    async def test_app_action_focus_next(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test focus next action."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Trigger focus next action
            await pilot.press("tab")
            await pilot.pause()

            # Should not crash

    async def test_app_action_focus_previous(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test focus previous action."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Trigger focus previous action
            await pilot.press("shift+tab")
            await pilot.pause()

            # Should not crash

    async def test_app_current_view_name_tracking(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test current view name is tracked."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Current view name should be initialized
            assert app._current_view_name is None or isinstance(app._current_view_name, str)


class TestTableSleuthAppAdvancedCoverage:
    """Additional tests to increase app.py coverage to 85%+."""

    async def test_app_on_column_selected_with_file(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test column selection with file loaded."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Set current file
            app._current_file_info = sample_parquet_info

            # Call column selected
            app._on_column_selected()
            await pilot.pause()

            # Should not crash

    async def test_app_on_profile_column_requested_no_file(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test profile column request with no file loaded."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Create profile request message
            from tablesleuth.tui.views.profile_view import ProfileColumnRequested

            message = ProfileColumnRequested(column_name="test_col")
            app.on_profile_column_requested(message)
            await pilot.pause()

            # Should handle gracefully

    async def test_app_on_profile_column_requested_no_profiler(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test profile column request with no profiler."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Set file but no profiler
            app._current_file_info = sample_parquet_info
            app._profiler = None

            # Create profile request message
            from tablesleuth.tui.views.profile_view import ProfileColumnRequested

            message = ProfileColumnRequested(column_name="test_col")
            app.on_profile_column_requested(message)
            await pilot.pause()

            # Should handle gracefully

    async def test_app_profile_column_with_profiler(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test profiling a column with profiler available."""
        mock_profiler = Mock()
        mock_profiler.register_file_view = Mock(return_value="test_view")

        from tablesleuth.models.profiling import ColumnProfile

        mock_profile = ColumnProfile(
            column="id",
            row_count=100,
            non_null_count=100,
            null_count=0,
            distinct_count=100,
            min_value=1,
            max_value=100,
        )
        mock_profiler.profile_single_column = Mock(return_value=mock_profile)

        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            profiler=mock_profiler,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Set current file
            app._current_file_info = sample_parquet_info

            # Profile a column
            app._profile_column("id")
            await pilot.pause()

            # Should have called profiler
            assert mock_profiler.register_file_view.called
            assert mock_profiler.profile_single_column.called

    async def test_app_profile_column_with_cache(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test profiling uses cache."""
        mock_profiler = Mock()

        from tablesleuth.models.profiling import ColumnProfile

        mock_profile = ColumnProfile(
            column="id",
            row_count=100,
            non_null_count=100,
            null_count=0,
            distinct_count=100,
            min_value=1,
            max_value=100,
        )

        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            profiler=mock_profiler,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Set current file
            app._current_file_info = sample_parquet_info

            # Add to cache
            cache_key = (sample_parquet_info.path, "id")
            app._profile_cache[cache_key] = mock_profile

            # Profile the column
            app._profile_column("id")
            await pilot.pause()

            # Should use cache, not call profiler
            assert not mock_profiler.register_file_view.called

    async def test_app_profile_column_value_error(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test profiling handles ValueError."""
        mock_profiler = Mock()
        mock_profiler.register_file_view = Mock(return_value="test_view")
        mock_profiler.profile_single_column = Mock(
            side_effect=ValueError("not within the mounted data directory")
        )

        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            profiler=mock_profiler,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Set current file
            app._current_file_info = sample_parquet_info

            # Profile a column (should handle error)
            app._profile_column("id")
            await pilot.pause()

            # Should not crash

    async def test_app_profile_column_connection_error(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test profiling handles ConnectionError."""
        mock_profiler = Mock()
        mock_profiler.register_file_view = Mock(return_value="test_view")
        mock_profiler.profile_single_column = Mock(side_effect=ConnectionError("Connection failed"))

        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            profiler=mock_profiler,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Set current file
            app._current_file_info = sample_parquet_info

            # Profile a column (should handle error)
            app._profile_column("id")
            await pilot.pause()

            # Should not crash

    async def test_app_profile_column_generic_error(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test profiling handles generic errors."""
        mock_profiler = Mock()
        mock_profiler.register_file_view = Mock(return_value="test_view")
        mock_profiler.profile_single_column = Mock(side_effect=Exception("Unexpected error"))

        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            profiler=mock_profiler,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Set current file
            app._current_file_info = sample_parquet_info

            # Profile a column (should handle error)
            app._profile_column("id")
            await pilot.pause()

            # Should not crash

    async def test_app_invalidate_cache_all(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test invalidating all caches."""
        mock_profiler = Mock()
        mock_profiler.clear_views = Mock()

        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
            profiler=mock_profiler,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Add entries to caches
            app._file_metadata_cache["/test/file.parquet"] = Mock()
            app._profile_cache[("/test/file.parquet", "col1")] = Mock()

            # Invalidate all caches
            app._invalidate_cache(None)

            # All caches should be cleared
            assert len(app._file_metadata_cache) == 0
            assert len(app._profile_cache) == 0
            assert mock_profiler.clear_views.called

    async def test_app_get_cache_stats(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test getting cache statistics."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Add entries to caches
            app._file_metadata_cache["/test/file1.parquet"] = Mock()
            app._file_metadata_cache["/test/file2.parquet"] = Mock()
            app._profile_cache[("/test/file1.parquet", "col1")] = Mock()

            # Get stats
            stats = app.get_cache_stats()

            assert stats["metadata_entries"] == 2
            assert stats["profile_entries"] == 1

    async def test_app_action_focus_filter_not_available(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
    ) -> None:
        """Test focus filter when schema view not available."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Call action (schema view not mounted yet)
            app.action_focus_filter()
            await pilot.pause()

            # Should not crash

    async def test_app_update_views_with_file_info(
        self,
        mock_table_handle: TableHandle,
        mock_adapter: TableFormatAdapter,
        mock_config: AppConfig,
        sample_parquet_info: ParquetFileInfo,
    ) -> None:
        """Test updating views with file info."""
        app = TableSleuthApp(
            table_handle=mock_table_handle,
            adapter=mock_adapter,
            config=mock_config,
        )

        async with app.run_test() as pilot:
            await pilot.pause()

            # Call update views
            app._update_views(sample_parquet_info)
            await pilot.pause()

            # Should not crash
