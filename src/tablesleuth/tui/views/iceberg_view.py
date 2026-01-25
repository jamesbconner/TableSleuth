"""Iceberg metadata viewer screen for Table Sleuth."""

from __future__ import annotations

import logging
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from tablesleuth.models.iceberg import (
    IcebergSnapshotDetails,
    IcebergSnapshotInfo,
    IcebergTableInfo,
)
from tablesleuth.services.iceberg_metadata_service import IcebergMetadataService
from tablesleuth.services.profiling.backend_base import ProfilingBackend
from tablesleuth.services.snapshot_performance_analyzer import (
    SnapshotPerformanceAnalyzer,
)
from tablesleuth.services.snapshot_test_manager import SnapshotTestManager
from tablesleuth.tui.views.data_sample_view import DataSampleView
from tablesleuth.tui.views.snapshot_comparison_view import (
    PerformanceTestView,
    SnapshotComparisonView,
)
from tablesleuth.tui.views.snapshot_detail_view import (
    SnapshotDeletesView,
    SnapshotFilesView,
    SnapshotOverviewView,
    SnapshotPropertiesView,
    SnapshotSchemaView,
)
from tablesleuth.tui.widgets import LoadingIndicator, Notification

logger = logging.getLogger(__name__)


class SnapshotListView(Container):
    """Widget for displaying a list of Iceberg snapshots.

    Displays snapshots in a DataTable with columns:
    - Snapshot ID
    - Timestamp
    - Operation
    - Records
    - Files
    - Deletes (indicator)

    Supports:
    - Single selection (default)
    - Multi-selection (compare mode)
    - Virtual scrolling for large lists
    - Visual indicators for snapshots with deletes
    """

    DEFAULT_CSS = """
    SnapshotListView {
        height: 100%;
        border: solid $primary;
    }

    SnapshotListView > Static#list-header {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    SnapshotListView > DataTable {
        height: 1fr;
    }
    """

    def __init__(
        self,
        snapshots: list[IcebergSnapshotInfo] | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the snapshot list view.

        Args:
            snapshots: Optional list of snapshots to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._snapshots = snapshots or []
        self._compare_mode = False

    def compose(self) -> ComposeResult:
        """Compose the snapshot list view."""
        yield Static("Snapshots", id="list-header")
        yield DataTable(id="snapshot-table", cursor_type="row")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        table = self.query_one("#snapshot-table", DataTable)

        # Add columns
        table.add_columns(
            "ID",
            "Timestamp",
            "Operation",
            "Records",
            "Files",
            "Deletes",
        )

        # Populate with initial data
        if self._snapshots:
            self.update_snapshots(self._snapshots)

    def update_snapshots(self, snapshots: list[IcebergSnapshotInfo]) -> None:
        """Update the displayed snapshots.

        Args:
            snapshots: List of IcebergSnapshotInfo objects
        """
        self._snapshots = snapshots
        table = self.query_one("#snapshot-table", DataTable)

        # Clear existing rows
        table.clear()

        # Add rows
        for snapshot in snapshots:
            # Format timestamp
            timestamp = datetime.fromtimestamp(snapshot.timestamp_ms / 1000)
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M")

            # Format record count
            records_str = f"{snapshot.total_records:,}"

            # Format file count
            files_str = f"{snapshot.total_data_files}"
            if snapshot.has_deletes:
                files_str += f" (+{snapshot.total_delete_files}D)"

            # Delete indicator
            delete_indicator = ""
            if snapshot.has_deletes:
                delete_ratio = snapshot.delete_ratio
                if delete_ratio > 15:
                    delete_indicator = "⚠️  High"
                elif delete_ratio > 5:
                    delete_indicator = "⚠️  Med"
                else:
                    delete_indicator = "⚠️  Low"

            # Add row
            table.add_row(
                str(snapshot.snapshot_id),
                timestamp_str,
                snapshot.operation,
                records_str,
                files_str,
                delete_indicator,
            )

    def clear(self) -> None:
        """Clear the snapshot list."""
        self._snapshots = []
        table = self.query_one("#snapshot-table", DataTable)
        table.clear()

    def set_compare_mode(self, enabled: bool) -> None:
        """Enable or disable compare mode.

        Args:
            enabled: True to enable compare mode, False to disable
        """
        self._compare_mode = enabled
        # Note: Multi-selection would require custom implementation
        # For now, we'll track selections in the parent screen

    def get_selected_snapshot_index(self) -> int | None:
        """Get the index of the currently selected snapshot.

        Returns:
            Index of selected snapshot, or None if no selection
        """
        table = self.query_one("#snapshot-table", DataTable)
        if table.cursor_row is not None and table.cursor_row >= 0:
            return table.cursor_row
        return None

    def get_selected_snapshot(self) -> IcebergSnapshotInfo | None:
        """Get the currently selected snapshot.

        Returns:
            Selected IcebergSnapshotInfo, or None if no selection
        """
        index = self.get_selected_snapshot_index()
        if index is not None and 0 <= index < len(self._snapshots):
            return self._snapshots[index]
        return None

    def get_snapshots(self) -> list[IcebergSnapshotInfo]:
        """Get all snapshots.

        Returns:
            List of all snapshots
        """
        return self._snapshots


class IcebergView(Screen):
    """Screen for viewing and comparing Iceberg table snapshots.

    Provides:
    - Snapshot list (left panel)
    - Snapshot details (right panel with tabs)
    - Compare mode for snapshot comparison
    - Performance testing capabilities
    """

    TITLE = "Table Sleuth - Iceberg Analysis"

    CSS = """
    IcebergView {
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

    #table-info {
        height: auto;
        padding: 1;
        background: $panel;
        border-bottom: solid $primary;
    }

    #compare-controls {
        height: auto;
        padding: 1;
        background: $surface;
        border-bottom: solid $primary;
    }

    #action-buttons {
        height: auto;
        padding: 1;
        background: $surface;
        border-top: solid $primary;
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
        padding: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("c", "toggle_compare", "Compare"),
        ("t", "run_test", "Test"),
        ("x", "cleanup", "Cleanup"),
        ("escape", "dismiss_notification", "Dismiss"),
    ]

    def __init__(
        self,
        table_info: IcebergTableInfo,
        metadata_service: IcebergMetadataService,
        profiler: ProfilingBackend | None = None,
        catalog_name: str | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the Iceberg viewer screen.

        Args:
            table_info: Iceberg table information
            metadata_service: Service for loading metadata
            profiler: Optional profiling backend for performance testing
            catalog_name: Catalog name for snapshot registration (defaults to "local")
            name: Screen name
            id: Screen ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._table_info = table_info
        self._metadata_service = metadata_service
        self._profiler = profiler
        self._catalog_name = catalog_name or "local"

        # Initialize managers
        self._test_manager: SnapshotTestManager | None = None
        self._performance_analyzer: SnapshotPerformanceAnalyzer | None = None

        # State
        self._snapshots: list[IcebergSnapshotInfo] = []
        self._selected_snapshot: IcebergSnapshotInfo | None = None
        self._selected_details: IcebergSnapshotDetails | None = None
        self._compare_mode = False
        self._selected_snapshots: list[IcebergSnapshotInfo] = []

        # Registered table names for performance testing
        self._registered_table_a: str | None = None
        self._registered_table_b: str | None = None

        # Cache for snapshot details
        self._details_cache: dict[int, IcebergSnapshotDetails] = {}

    def compose(self) -> ComposeResult:
        """Compose the Iceberg viewer screen."""
        yield Header()
        yield Notification(id="notification")
        yield LoadingIndicator(id="loading")

        with Horizontal():
            # Left panel: Snapshot list and controls
            with Vertical(id="left-panel"):
                # Table info header
                yield Static(self._format_table_info(), id="table-info")

                # Compare mode controls
                with Container(id="compare-controls"):
                    yield Checkbox("Compare Mode", id="compare-checkbox")

                # Snapshot list
                yield SnapshotListView(id="snapshot-list")

                # Action buttons
                with Container(id="action-buttons"):
                    yield Button("Cleanup Test Tables", id="cleanup-button", variant="warning")

            # Right panel: Tabbed detail views
            with Vertical(id="right-panel"):
                with TabbedContent(id="detail-tabs"):
                    with TabPane("Overview", id="overview-tab"):
                        yield SnapshotOverviewView(id="overview-view")

                    with TabPane("Files", id="files-tab"):
                        yield SnapshotFilesView(id="files-view")

                    with TabPane("Schema", id="schema-tab"):
                        yield SnapshotSchemaView(id="schema-view")

                    with TabPane("Deletes", id="deletes-tab"):
                        yield SnapshotDeletesView(id="deletes-view")

                    with TabPane("Properties", id="properties-tab"):
                        yield SnapshotPropertiesView(id="properties-view")

                    with TabPane("Data Sample", id="data-sample-tab"):
                        yield DataSampleView(id="data-sample-view")

                    with TabPane("Compare", id="compare-tab", disabled=True):
                        yield SnapshotComparisonView(id="comparison-view")

                    with TabPane("Performance Test", id="perf-test-tab", disabled=True):
                        yield PerformanceTestView(id="perf-test-view")

        yield Footer()

    def on_mount(self) -> None:
        """Set up the screen when mounted."""
        # Load snapshots
        self._load_snapshots()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle snapshot selection in the list.

        Args:
            event: Row selection event
        """
        # Get the selected snapshot
        snapshot_list = self.query_one("#snapshot-list", SnapshotListView)
        selected_snapshot = snapshot_list.get_selected_snapshot()

        if selected_snapshot:
            if self._compare_mode:
                # In compare mode, track multiple selections
                if selected_snapshot not in self._selected_snapshots:
                    self._selected_snapshots.append(selected_snapshot)

                    # Limit to 2 snapshots
                    if len(self._selected_snapshots) > 2:
                        self._selected_snapshots.pop(0)

                    # Update compare mode UI
                    self._update_compare_mode()
            else:
                # Normal mode: single selection
                self._selected_snapshot = selected_snapshot
                self._load_snapshot_details(selected_snapshot)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle compare mode checkbox change.

        Args:
            event: Checkbox change event
        """
        if event.checkbox.id == "compare-checkbox":
            self._compare_mode = event.value

            # Clear selections when toggling
            self._selected_snapshots = []

            # Update UI
            self._update_compare_mode()

            # Show notification
            notification = self.query_one("#notification", Notification)
            if self._compare_mode:
                notification.info("Compare mode enabled. Select 2 snapshots to compare.")
            else:
                notification.info("Compare mode disabled.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button press event
        """
        if event.button.id == "cleanup-button":
            self._cleanup_test_tables()
        elif event.button.id == "run-test-button":
            self._run_performance_test()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle query template selection.

        Args:
            event: Select change event
        """
        if event.select.id == "query-template-select" and event.value:
            # Get predefined query
            if self._performance_analyzer and isinstance(event.value, str):
                queries = self._performance_analyzer.get_predefined_queries()
                if event.value in queries:
                    query_input = self.query_one("#query-input", Input)
                    query_input.value = queries[event.value]

    def _format_table_info(self) -> str:
        """Format table information for display.

        Returns:
            Formatted table info string
        """
        lines = [
            f"[bold]Table:[/bold] {self._table_info.table_uuid[:8]}...",
            f"[bold]Location:[/bold] {self._table_info.location}",
            f"[bold]Format:[/bold] v{self._table_info.format_version}",
        ]
        return "\n".join(lines)

    def _load_snapshots(self) -> None:
        """Load snapshots from the table."""
        loading = self.query_one("#loading", LoadingIndicator)
        loading.show("Loading snapshots...")

        try:
            # Load snapshots using metadata service
            self._snapshots = self._metadata_service.list_snapshots(self._table_info)

            # Update snapshot list view
            snapshot_list = self.query_one("#snapshot-list", SnapshotListView)
            snapshot_list.update_snapshots(self._snapshots)

            # Show success notification
            notification = self.query_one("#notification", Notification)
            notification.success(f"Loaded {len(self._snapshots)} snapshots")

        except Exception as e:
            logger.exception("Failed to load snapshots")
            notification = self.query_one("#notification", Notification)
            notification.error(f"Failed to load snapshots: {e}")

        finally:
            loading.hide()

    def _load_snapshot_details(self, snapshot: IcebergSnapshotInfo) -> None:
        """Load detailed information for a snapshot.

        Args:
            snapshot: Snapshot to load details for
        """
        # Check cache first
        if snapshot.snapshot_id in self._details_cache:
            self._selected_details = self._details_cache[snapshot.snapshot_id]
            self._update_detail_views()
            return

        loading = self.query_one("#loading", LoadingIndicator)
        loading.show(f"Loading snapshot {snapshot.snapshot_id}...")

        try:
            # Load snapshot details
            details = self._metadata_service.get_snapshot_details(
                self._table_info, snapshot.snapshot_id
            )

            # Cache the details
            self._details_cache[snapshot.snapshot_id] = details
            self._selected_details = details

            # Update detail views
            self._update_detail_views()

        except Exception as e:
            logger.exception(f"Failed to load snapshot details: {e}")
            notification = self.query_one("#notification", Notification)
            notification.error(f"Failed to load snapshot details: {e}")

        finally:
            loading.hide()

    def _update_detail_views(self) -> None:
        """Update all detail views with current snapshot data."""
        if not self._selected_snapshot or not self._selected_details:
            return

        # Update overview
        overview = self.query_one("#overview-view", SnapshotOverviewView)
        overview.update_snapshot(self._selected_snapshot)

        # Update files
        files = self.query_one("#files-view", SnapshotFilesView)
        files.update_details(self._selected_details)

        # Update schema
        schema = self.query_one("#schema-view", SnapshotSchemaView)
        schema.update_schema(self._selected_details.schema)

        # Update deletes
        deletes = self.query_one("#deletes-view", SnapshotDeletesView)
        deletes.update_details(self._selected_details)

        # Update properties
        properties = self.query_one("#properties-view", SnapshotPropertiesView)
        properties.update_snapshot(self._selected_snapshot)

        # Update data sample view with first data file
        data_sample = self.query_one("#data-sample-view", DataSampleView)
        if self._selected_details.data_files:
            # Get the first data file for sampling
            first_file = self._selected_details.data_files[0]
            file_path = first_file["file_path"]

            # Load the file info using the parquet inspector
            try:
                from tablesleuth.services.filesystem import FileSystem
                from tablesleuth.services.parquet_service import ParquetInspector

                # Ensure the file exists (supports both local and S3 paths)
                fs = FileSystem()  # Uses AWS_REGION env var or defaults
                if not fs.exists(file_path):
                    logger.warning(f"Data file not found: {file_path}")
                    data_sample.clear()
                    return

                parquet_inspector = ParquetInspector()  # Uses AWS_REGION env var or defaults
                file_info = parquet_inspector.inspect_file(file_path)
                data_sample.update_file_info(file_info)
            except Exception as e:
                logger.error(f"Failed to load data sample from {file_path}: {e}", exc_info=True)
                data_sample.clear()
        else:
            data_sample.clear()

    def action_refresh(self) -> None:
        """Refresh the snapshot list."""
        self._load_snapshots()

    def action_toggle_compare(self) -> None:
        """Toggle compare mode."""
        checkbox = self.query_one("#compare-checkbox", Checkbox)
        checkbox.toggle()

    def action_run_test(self) -> None:
        """Run performance test (placeholder)."""
        notification = self.query_one("#notification", Notification)
        notification.info("Performance testing not yet implemented")

    def action_cleanup(self) -> None:
        """Cleanup test tables."""
        self._cleanup_test_tables()

    def action_dismiss_notification(self) -> None:
        """Dismiss the notification."""
        notification = self.query_one("#notification", Notification)
        notification.dismiss()

    def action_quit(self) -> None:
        """Quit the screen."""
        self.app.exit()

    def _update_compare_mode(self) -> None:
        """Update UI based on compare mode state."""
        # Enable/disable compare tab
        tabs = self.query_one("#detail-tabs", TabbedContent)
        compare_tab = self.query_one("#compare-tab", TabPane)
        perf_tab = self.query_one("#perf-test-tab", TabPane)

        if len(self._selected_snapshots) == 2:
            # Enable compare and performance test tabs
            compare_tab.disabled = False
            perf_tab.disabled = False

            # Register snapshots and run comparison
            self._register_snapshots_for_comparison()
        else:
            # Disable tabs
            compare_tab.disabled = True
            perf_tab.disabled = True

            # Clear registered table names
            self._registered_table_a = None
            self._registered_table_b = None

    def _register_snapshots_for_comparison(self) -> None:
        """Register selected snapshots as tables for comparison."""
        if len(self._selected_snapshots) != 2:
            return

        loading = self.query_one("#loading", LoadingIndicator)
        loading.show("Registering snapshots for comparison...")

        try:
            # Initialize test manager if needed
            if self._test_manager is None:
                self._test_manager = SnapshotTestManager(catalog_name=self._catalog_name)
                self._test_manager.ensure_snapshot_namespace()

            # Register both snapshots
            snapshot_a, snapshot_b = self._selected_snapshots

            self._registered_table_a = self._test_manager.register_snapshot(
                self._table_info.metadata_location,
                snapshot_a.snapshot_id,
            )

            self._registered_table_b = self._test_manager.register_snapshot(
                self._table_info.metadata_location,
                snapshot_b.snapshot_id,
            )

            # Initialize performance analyzer if needed
            if self._performance_analyzer is None and self._profiler:
                self._performance_analyzer = SnapshotPerformanceAnalyzer(self._profiler)

            # Register the Iceberg tables with the profiler for query execution
            # Pass the metadata location along with snapshot IDs
            if self._profiler is not None:
                if hasattr(self._profiler, "register_iceberg_table_with_snapshot"):
                    self._profiler.register_iceberg_table_with_snapshot(
                        self._registered_table_a,
                        self._table_info.metadata_location,
                        snapshot_a.snapshot_id,
                    )
                    self._profiler.register_iceberg_table_with_snapshot(
                        self._registered_table_b,
                        self._table_info.metadata_location,
                        snapshot_b.snapshot_id,
                    )
                    logger.debug("Registered Iceberg tables with snapshots for profiler")
                elif hasattr(self._profiler, "register_iceberg_table"):
                    # Fallback for older API
                    self._profiler.register_iceberg_table(
                        self._registered_table_a, self._table_info.metadata_location
                    )
                    self._profiler.register_iceberg_table(
                        self._registered_table_b, self._table_info.metadata_location
                    )
                    logger.debug("Registered Iceberg tables with profiler")

            # Run comparison
            comparison = self._metadata_service.compare_snapshots(
                self._table_info,
                snapshot_a.snapshot_id,
                snapshot_b.snapshot_id,
            )

            # Update comparison view
            comparison_view = self.query_one("#comparison-view", SnapshotComparisonView)
            comparison_view.update_comparison(comparison)

            # Update performance test view with table names
            if self._performance_analyzer:
                perf_view = self.query_one("#perf-test-view", PerformanceTestView)
                perf_view.set_table_names(self._registered_table_a, self._registered_table_b)

            # Show success notification
            notification = self.query_one("#notification", Notification)
            notification.success("Snapshots registered for comparison")

        except Exception as e:
            logger.exception("Failed to register snapshots")
            notification = self.query_one("#notification", Notification)
            notification.error(f"Failed to register snapshots: {e}")

        finally:
            loading.hide()

    def _run_performance_test(self) -> None:
        """Run performance test with current query."""
        if not self._performance_analyzer or len(self._selected_snapshots) != 2:
            notification = self.query_one("#notification", Notification)
            notification.warning("Performance testing requires 2 selected snapshots")
            return

        # Get query from input
        query_input = self.query_one("#query-input", Input)
        query = query_input.value.strip()

        if not query:
            notification = self.query_one("#notification", Notification)
            notification.warning("Please enter a query")
            return

        loading = self.query_one("#loading", LoadingIndicator)
        loading.show("Running performance test...")

        try:
            # Use the registered table names
            if not self._registered_table_a or not self._registered_table_b:
                notification = self.query_one("#notification", Notification)
                notification.error("Snapshots not registered. Please re-enable compare mode.")
                return

            # Get full snapshot info from selected snapshots
            snapshot_a, snapshot_b = self._selected_snapshots

            # Run comparison with full snapshot info for comprehensive analysis
            comparison = self._performance_analyzer.compare_query_performance(
                self._registered_table_a,
                self._registered_table_b,
                query,
                snapshot_a_info=snapshot_a,
                snapshot_b_info=snapshot_b,
            )

            # Update results view
            perf_view = self.query_one("#perf-test-view", PerformanceTestView)
            perf_view.update_results(comparison)

            # Show success notification
            notification = self.query_one("#notification", Notification)
            notification.success("Performance test completed")

        except Exception as e:
            logger.exception("Failed to run performance test")
            notification = self.query_one("#notification", Notification)
            notification.error(f"Performance test failed: {e}")

        finally:
            loading.hide()

    def _cleanup_test_tables(self) -> None:
        """Cleanup registered test tables."""
        if self._test_manager is None:
            notification = self.query_one("#notification", Notification)
            notification.info("No test tables to cleanup")
            return

        loading = self.query_one("#loading", LoadingIndicator)
        loading.show("Cleaning up test tables...")

        try:
            # Cleanup all tables
            self._test_manager.cleanup_tables()

            # Reset state
            self._selected_snapshots = []
            self._compare_mode = False

            # Update checkbox
            checkbox = self.query_one("#compare-checkbox", Checkbox)
            checkbox.value = False

            # Disable compare tabs
            self._update_compare_mode()

            # Show success notification
            notification = self.query_one("#notification", Notification)
            notification.success("Test tables cleaned up")

        except Exception as e:
            logger.exception("Failed to cleanup test tables")
            notification = self.query_one("#notification", Notification)
            notification.error(f"Cleanup failed: {e}")

        finally:
            loading.hide()
