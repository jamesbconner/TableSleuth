from __future__ import annotations

import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from tablesleuth.config import AppConfig
from tablesleuth.models import TableHandle
from tablesleuth.models.file_ref import FileRef
from tablesleuth.models.parquet import ParquetFileInfo
from tablesleuth.models.profiling import ColumnProfile
from tablesleuth.services.formats.base import TableFormatAdapter
from tablesleuth.services.parquet_service import ParquetInspector
from tablesleuth.services.profiling.backend_base import ProfilingBackend
from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler
from tablesleuth.tui.views import (
    DataSampleView,
    FileDetailView,
    FileListView,
    ProfileView,
    RowGroupsView,
    SchemaView,
    StructureView,
)
from tablesleuth.tui.views.profile_view import ProfileColumnRequested
from tablesleuth.tui.widgets import LoadingIndicator, Notification

logger = logging.getLogger(__name__)


class TableSleuthApp(App):
    """Table Sleuth TUI application for Parquet file inspection.

    Provides a multi-panel interface for exploring Parquet files with:
    - File list view (left panel)
    - Tabbed detail views (right panel):
      - File details
      - Schema
      - Row groups
      - Column statistics
      - Profile results
    """

    TITLE = "Table Sleuth - Parquet Analysis"
    SUB_TITLE = ""

    CSS = """
    Screen {
        layout: horizontal;
    }

    #left-panel {
        width: 40%;
        height: 100%;
    }

    #right-panel {
        width: 60%;
        height: 100%;
    }

    TabbedContent {
        height: 100%;
    }

    TabbedContent ContentSwitcher {
        height: 100%;
    }

    TabPane {
        height: 100%;
        overflow-y: auto;
    }

    #loading-indicator {
        background: $accent;
        color: $text;
        padding: 0 1;
        text-style: italic;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("f", "focus_filter", "Filter"),
        ("tab", "focus_next", "Next Tab"),
        ("shift+tab", "focus_previous", "Prev Tab"),
        ("escape", "dismiss_notification", "Dismiss"),
    ]

    def __init__(
        self,
        table_handle: TableHandle,
        adapter: TableFormatAdapter,
        config: AppConfig,
        files: list[FileRef] | None = None,
        profiler: ProfilingBackend | None = None,
    ) -> None:
        """Initialize the Table Sleuth app.

        Args:
            table_handle: Table handle (for future use)
            adapter: Table format adapter (for future use)
            config: Application configuration
            files: Optional list of files to display
            profiler: Optional profiling backend (GizmoSQL by default)
        """
        super().__init__()
        self.table_handle = table_handle
        self.adapter = adapter
        self.config = config
        self._files = files or []
        self._inspector = ParquetInspector()  # Uses AWS_REGION env var or defaults
        self._current_file_info: ParquetFileInfo | None = None
        self._current_view_name: str | None = None

        # Initialize caching
        self._file_metadata_cache: dict[str, ParquetFileInfo] = {}
        self._profile_cache: dict[
            tuple[str, str], ColumnProfile
        ] = {}  # (file_path, column) -> ColumnProfile

        # Initialize profiling backend
        if profiler is None:
            try:
                self._profiler: ProfilingBackend | None = GizmoDuckDbProfiler(
                    uri=config.gizmosql.uri,
                    username=config.gizmosql.username,
                    password=config.gizmosql.password,
                    tls_skip_verify=config.gizmosql.tls_skip_verify,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize profiling backend: {e}")
                self._profiler = None
        else:
            self._profiler = profiler

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        yield Header()
        yield Notification(id="notification")
        yield LoadingIndicator(id="loading")

        with Horizontal():
            # Left panel: File list
            with Vertical(id="left-panel"):
                yield FileListView(files=self._files, id="file-list")

            # Right panel: Tabbed detail views
            with Vertical(id="right-panel"):
                with TabbedContent():
                    with TabPane("File Detail"):
                        yield FileDetailView(id="file-detail")
                    with TabPane("Schema"):
                        yield SchemaView(id="schema")
                    with TabPane("Row Groups"):
                        yield RowGroupsView(id="row-groups")
                    with TabPane("Structure"):
                        yield StructureView(id="structure")
                    with TabPane("Data Sample"):
                        yield DataSampleView(id="data-sample")
                    with TabPane("Profile"):
                        yield ProfileView(id="profile")

        yield Footer()

    def on_mount(self) -> None:
        """Set up the app when mounted."""
        # Show aggregate stats if files are loaded
        if self._files:
            file_list = self.query_one("#file-list", FileListView)
            file_list.show_aggregate_stats()

            # Auto-select first file for immediate inspection
            # Capture first file to avoid race condition with list mutation
            first_file = self._files[0]
            self.set_timer(0.1, lambda: self._inspect_file(first_file))

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        """Handle tab activation - update view when tab becomes visible.

        Args:
            event: Tab activated event
        """
        if self._current_file_info is None:
            return

        # Update the view in the newly activated tab
        tab_id = event.tab.id
        logger.debug(f"Tab activated: {tab_id}")

        try:
            if "file-detail" in str(tab_id):
                file_detail = self.query_one("#file-detail", FileDetailView)
                file_detail.update_file_info(self._current_file_info)
            elif "schema" in str(tab_id):
                schema = self.query_one("#schema", SchemaView)
                schema.update_schema(self._current_file_info)
            elif "row-groups" in str(tab_id):
                row_groups = self.query_one("#row-groups", RowGroupsView)
                row_groups.update_row_groups(self._current_file_info)
            elif "structure" in str(tab_id):
                structure = self.query_one("#structure", StructureView)
                structure.update_structure(self._current_file_info)
        except Exception as e:
            logger.debug(f"Could not update view for tab {tab_id}: {e}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in data tables.

        Args:
            event: Row selected event from DataTable
        """
        # Handle file list selection
        if event.data_table.id == "file-list-table":
            file_list = self.query_one("#file-list", FileListView)
            selected_file = file_list.get_selected_file()

            if selected_file:
                self._inspect_file(selected_file)

        # Handle schema table selection (column selection)
        elif event.data_table.id == "schema-table":
            self._on_column_selected()

    def _inspect_file(self, file_ref: FileRef) -> None:
        """Inspect a Parquet file and update all views.

        Uses caching to avoid re-inspecting the same file.

        Args:
            file_ref: FileRef to inspect
        """
        try:
            # Show loading indicator
            self._show_loading(f"Inspecting {Path(file_ref.path).name}...")

            # Check cache first
            if file_ref.path in self._file_metadata_cache:
                logger.debug(f"Using cached metadata for {file_ref.path}")
                file_info = self._file_metadata_cache[file_ref.path]
            else:
                # Inspect file
                file_info = self._inspector.inspect_file(file_ref.path)

                # Cache the result
                self._file_metadata_cache[file_ref.path] = file_info
                logger.debug(f"Cached metadata for {file_ref.path}")

            # Store current file info
            self._current_file_info = file_info

            # Clear view name to force re-registration for profiling
            self._current_view_name = None

            # Update all views
            self._update_views(file_info)

            # Clear loading indicator
            self._clear_loading()

            # Show success notification
            try:
                notification = self.query_one("#notification", Notification)
                notification.success(f"Loaded {Path(file_ref.path).name}", duration=3.0)
            except Exception as e:
                logger.debug(f"Could not show notification: {e}")

        except FileNotFoundError as e:
            logger.error(f"File not found: {e}")
            self._show_error(f"File not found: {file_ref.path}")
        except ValueError as e:
            logger.error(f"Invalid Parquet file: {e}")
            self._show_error(f"Invalid Parquet file: {e}")
        except Exception as e:
            logger.exception("Error inspecting file")
            self._show_error(f"Error inspecting file: {e}")

    def _update_views(self, file_info: ParquetFileInfo) -> None:
        """Update all detail views with file information.

        Args:
            file_info: ParquetFileInfo to display
        """
        logger.debug(
            f"Updating views with file info: {file_info.path}, {file_info.num_rows} rows, {file_info.num_columns} columns"
        )

        # Try to update each view, but don't fail if they're not mounted yet
        # (TabbedContent only mounts active tab content)

        try:
            file_detail = self.query_one("#file-detail", FileDetailView)
            file_detail.update_file_info(file_info)
            logger.debug("Updated file detail view")
        except Exception as e:
            logger.debug(f"File detail view not available: {e}")

        try:
            schema = self.query_one("#schema", SchemaView)
            schema.update_schema(file_info)
            logger.debug("Updated schema view")
        except Exception as e:
            logger.debug(f"Schema view not available: {e}")

        try:
            row_groups = self.query_one("#row-groups", RowGroupsView)
            row_groups.update_row_groups(file_info)
            logger.debug("Updated row groups view")
        except Exception as e:
            logger.debug(f"Row groups view not available: {e}")

        try:
            structure = self.query_one("#structure", StructureView)
            structure.update_structure(file_info)
            logger.debug("Updated structure view")
        except Exception as e:
            logger.debug(f"Structure view not available: {e}")

        try:
            data_sample = self.query_one("#data-sample", DataSampleView)
            data_sample.update_file_info(file_info)
            logger.debug("Updated data sample view")
        except Exception as e:
            logger.debug(f"Data sample view not available: {e}")

        try:
            profile = self.query_one("#profile", ProfileView)
            profile.update_file_info(file_info)
            logger.debug("Updated profile view with file info")
        except Exception as e:
            logger.debug(f"Profile view not available: {e}")

        # Note: Views in inactive tabs won't be mounted yet.
        # They will be updated when the user switches to those tabs.

    def _show_loading(self, message: str) -> None:
        """Show loading indicator.

        Args:
            message: Loading message to display
        """
        logger.debug(message)
        try:
            loading = self.query_one("#loading", LoadingIndicator)
            loading.show(message)
        except Exception as e:
            # Widget not mounted yet
            logger.debug(f"Could not show loading indicator: {e}")

    def _clear_loading(self) -> None:
        """Clear loading indicator."""
        try:
            loading = self.query_one("#loading", LoadingIndicator)
            loading.hide()
        except Exception as e:
            # Widget not mounted yet
            logger.debug(f"Could not hide loading indicator: {e}")

    def _show_error(self, message: str) -> None:
        """Show error message to user.

        Args:
            message: Error message to display
        """
        logger.error(message)

        # Show error notification
        try:
            notification = self.query_one("#notification", Notification)
            notification.error(message, duration=10.0)
        except Exception as e:
            # Widget not mounted yet
            logger.debug(f"Could not show error notification: {e}")

        # Clear loading indicator
        self._clear_loading()

        # Clear all views if app is mounted
        try:
            file_detail = self.query_one("#file-detail", FileDetailView)
            file_detail.clear()

            schema = self.query_one("#schema", SchemaView)
            schema.clear()

            row_groups = self.query_one("#row-groups", RowGroupsView)
            row_groups.clear()

            structure = self.query_one("#structure", StructureView)
            structure.clear()

            data_sample = self.query_one("#data-sample", DataSampleView)
            data_sample.clear()

            profile = self.query_one("#profile", ProfileView)
            profile.clear()
        except Exception as e:
            # App not mounted yet, ignore
            logger.debug(f"Could not clear profile view: {e}")

    def _on_column_selected(self) -> None:
        """Handle column selection in schema view."""
        if self._current_file_info is None:
            return

        # Get selected column
        schema = self.query_one("#schema", SchemaView)
        column_name = schema.get_selected_column()

        if column_name is None:
            return

        # Find column stats for this column
        column_stats = None
        for col in self._current_file_info.columns:
            if col.name == column_name:
                column_stats = col
                break

        # Column stats are now shown in the Schema view detail panel
        # No need to update a separate view

    def on_profile_column_requested(self, message: ProfileColumnRequested) -> None:
        """Handle profile column request from ProfileView.

        Args:
            message: ProfileColumnRequested message with column name
        """
        if self._current_file_info is None:
            logger.warning("No file selected for profiling")
            try:
                profile = self.query_one("#profile", ProfileView)
                profile.show_error("No file loaded")
            except Exception as e:
                logger.debug(f"Could not show error in profile view: {e}")
            return

        if self._profiler is None:
            logger.warning("Profiling backend not available")
            try:
                profile = self.query_one("#profile", ProfileView)
                profile.show_error("Profiling backend not available")
            except Exception as e:
                logger.debug(f"Could not show error in profile view: {e}")
            return

        # Trigger profiling for the requested column
        self._profile_column(message.column_name)

    def _profile_column(self, column_name: str) -> None:
        """Profile a column using the profiling backend.

        Uses caching to avoid re-profiling the same column.

        Args:
            column_name: Name of column to profile
        """
        if self._profiler is None or self._current_file_info is None:
            return

        try:
            # Check cache first
            cache_key = (self._current_file_info.path, column_name)
            if cache_key in self._profile_cache:
                logger.debug(f"Using cached profile for {column_name}")
                profile_result = self._profile_cache[cache_key]
            else:
                # Register file view if not already registered
                if self._current_view_name is None:
                    # Pass local path directly - profiler handles Docker conversion if needed
                    logger.debug(f"Registering file view: {self._current_file_info.path}")
                    self._current_view_name = self._profiler.register_file_view(
                        [self._current_file_info.path]
                    )

                # Profile the column
                profile_result = self._profiler.profile_single_column(
                    self._current_view_name,
                    column_name,
                )

                # Cache the result
                self._profile_cache[cache_key] = profile_result
                logger.debug(f"Cached profile for {column_name}")

            # Update profile view
            profile = self.query_one("#profile", ProfileView)
            profile.update_profile(profile_result)

        except ValueError as e:
            logger.error(f"Profiling error: {e}")
            profile = self.query_one("#profile", ProfileView)

            # Provide helpful error message for path validation failures
            error_msg = str(e)
            if "not within the mounted data directory" in error_msg:
                error_msg += (
                    "\n\nThis error occurs when using Docker GizmoSQL. "
                    "Please ensure:\n"
                    "1. The file is within your configured data directory\n"
                    "2. Docker volume mount matches your configuration\n"
                    "3. Check local_data_path and docker_data_path in tablesleuth.toml"
                )

            profile.show_error(error_msg)
        except ConnectionError as e:
            logger.error(f"GizmoSQL connection error: {e}")
            profile = self.query_one("#profile", ProfileView)

            # Provide deployment-specific guidance
            error_msg = (
                "GizmoSQL connection failed. Please ensure GizmoSQL is running.\n\n"
                "Start GizmoSQL:\n"
                "gizmosql_server -U username -P password -Q -T ~/.certs/cert0.pem ~/.certs/cert0.key\n\n"
                "Or install via: pip install gizmosql"
            )

            profile.show_error(error_msg)
        except Exception as e:
            logger.exception("Error profiling column")
            profile = self.query_one("#profile", ProfileView)
            profile.show_error(f"Profiling failed: {e}")

    def action_focus_filter(self) -> None:
        """Focus the schema filter input."""
        try:
            schema = self.query_one("#schema", SchemaView)
            filter_input = schema.query_one("#schema-filter")
            filter_input.focus()
        except Exception:
            # Schema view not available or not mounted
            logger.debug("Cannot focus filter: schema view not available")

    def action_dismiss_notification(self) -> None:
        """Dismiss the current notification."""
        try:
            notification = self.query_one("#notification", Notification)
            notification.dismiss()
        except Exception as e:
            # Notification not available
            logger.debug(f"Could not dismiss notification: {e}")

    def action_refresh(self) -> None:
        """Refresh the current view.

        Invalidates caches and re-inspects the current file.
        """
        # Re-inspect current file if one is selected
        if self._current_file_info:
            file_list = self.query_one("#file-list", FileListView)
            selected_file = file_list.get_selected_file()
            if selected_file:
                # Invalidate caches for this file
                self._invalidate_cache(selected_file.path)

                # Clear view name to force re-registration
                self._current_view_name = None

                # Re-inspect file
                self._inspect_file(selected_file)

    def _invalidate_cache(self, file_path: str | None = None) -> None:
        """Invalidate cached data.

        Args:
            file_path: Optional file path to invalidate. If None, clears all caches.
        """
        if file_path is None:
            # Clear all caches
            self._file_metadata_cache.clear()
            self._profile_cache.clear()

            # Clear profiler's view mappings
            if self._profiler is not None:
                self._profiler.clear_views()

            logger.debug("Cleared all caches")
        else:
            # Clear caches for specific file
            if file_path in self._file_metadata_cache:
                del self._file_metadata_cache[file_path]
                logger.debug(f"Cleared metadata cache for {file_path}")

            # Clear profile cache entries for this file
            keys_to_remove = [key for key in self._profile_cache.keys() if key[0] == file_path]
            for key in keys_to_remove:
                del self._profile_cache[key]

            if keys_to_remove:
                logger.debug(f"Cleared {len(keys_to_remove)} profile cache entries for {file_path}")

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "metadata_entries": len(self._file_metadata_cache),
            "profile_entries": len(self._profile_cache),
        }
