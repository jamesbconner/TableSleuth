"""Delta Lake viewer screen for Table Sleuth."""

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
    Static,
    TabbedContent,
    TabPane,
)

from tablesleuth.models import SnapshotInfo, TableHandle
from tablesleuth.services.delta_forensics import DeltaForensics
from tablesleuth.services.formats.delta import DeltaAdapter
from tablesleuth.tui.views.data_sample_view import DataSampleView
from tablesleuth.tui.widgets import LoadingIndicator, Notification

logger = logging.getLogger(__name__)


class VersionListView(Container):
    """Widget for displaying Delta Lake version history.

    Displays versions in a DataTable with columns:
    - Version
    - Timestamp
    - Operation
    - Files
    - Records
    """

    DEFAULT_CSS = """
    VersionListView {
        height: 1fr;
        border: solid $primary;
        overflow: hidden;
    }

    VersionListView > Static#list-header {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
        height: auto;
    }

    VersionListView > DataTable {
        height: 1fr;
        overflow-y: auto;
        scrollbar-size: 1 1;
    }
    """

    def __init__(
        self,
        versions: list[SnapshotInfo] | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the version list view.

        Args:
            versions: Optional list of versions to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._versions = versions or []
        self._versions_with_metadata: set[int] = set()

    def compose(self) -> ComposeResult:
        """Compose the version list view."""
        yield Static("Version History (* = schema change)", id="list-header")
        yield DataTable(id="version-table", cursor_type="row")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        table = self.query_one("#version-table", DataTable)

        # Enable scrollbars
        table.show_vertical_scrollbar = True
        table.show_horizontal_scrollbar = False

        # Add columns (added Schema column to indicate metadata presence)
        table.add_columns(
            "Version",
            "Timestamp",
            "Operation",
            "Files",
            "Records",
            "Schema",  # Indicator for versions with metaData
        )

        # Populate with initial data
        if self._versions:
            self.update_versions(self._versions)

    def set_versions_with_metadata(self, versions_with_metadata: set[int]) -> None:
        """Set which versions have metaData entries.

        Args:
            versions_with_metadata: Set of version numbers with metaData
        """
        self._versions_with_metadata = versions_with_metadata
        # Refresh display if we already have versions
        if self._versions:
            self.update_versions(self._versions)

    def update_versions(self, versions: list[SnapshotInfo]) -> None:
        """Update the displayed versions.

        Args:
            versions: List of SnapshotInfo objects
        """
        self._versions = versions
        table = self.query_one("#version-table", DataTable)

        # Clear existing rows
        table.clear()

        # Add rows (most recent first)
        for snapshot in reversed(versions):
            # Format timestamp
            timestamp = datetime.fromtimestamp(snapshot.timestamp_ms / 1000)
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M")

            # Format file count
            files_str = str(len(snapshot.data_files))

            # Format record count
            total_records = sum(
                f.record_count for f in snapshot.data_files if f.record_count is not None
            )
            records_str = f"{total_records:,}" if total_records > 0 else "N/A"

            # Schema change indicator
            schema_indicator = "*" if snapshot.snapshot_id in self._versions_with_metadata else ""

            # Add row
            table.add_row(
                str(snapshot.snapshot_id),
                timestamp_str,
                snapshot.operation,
                files_str,
                records_str,
                schema_indicator,
            )

    def clear(self) -> None:
        """Clear the version list."""
        self._versions = []
        table = self.query_one("#version-table", DataTable)
        table.clear()

    def get_selected_version_index(self) -> int | None:
        """Get the index of the currently selected version.

        Returns:
            Index of selected version, or None if no selection
        """
        table = self.query_one("#version-table", DataTable)
        if table.cursor_row is not None and table.cursor_row >= 0:
            # Reverse index since we display most recent first
            return len(self._versions) - 1 - table.cursor_row
        return None

    def get_selected_version(self) -> SnapshotInfo | None:
        """Get the currently selected version.

        Returns:
            Selected SnapshotInfo, or None if no selection
        """
        index = self.get_selected_version_index()
        if index is not None and 0 <= index < len(self._versions):
            return self._versions[index]
        return None

    def get_versions(self) -> list[SnapshotInfo]:
        """Get all versions.

        Returns:
            List of all versions
        """
        return self._versions


class VersionDetailView(Container):
    """Widget for displaying version details."""

    DEFAULT_CSS = """
    VersionDetailView {
        height: 100%;
        padding: 1;
    }

    VersionDetailView > Static {
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the version detail view."""
        super().__init__(name=name, id=id, classes=classes)
        self._version: SnapshotInfo | None = None

    def compose(self) -> ComposeResult:
        """Compose the version detail view."""
        yield Static("Select a version to view details", id="detail-content")

    def update_version(self, version: SnapshotInfo) -> None:
        """Update the displayed version details.

        Args:
            version: SnapshotInfo to display
        """
        self._version = version

        # Format details
        timestamp = datetime.fromtimestamp(version.timestamp_ms / 1000)
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        total_records = sum(
            f.record_count for f in version.data_files if f.record_count is not None
        )
        total_bytes = sum(f.file_size_bytes for f in version.data_files)

        lines = [
            f"[bold]Version:[/bold] {version.snapshot_id}",
            f"[bold]Timestamp:[/bold] {timestamp_str}",
            f"[bold]Operation:[/bold] {version.operation}",
            "",
            f"[bold]Data Files:[/bold] {len(version.data_files)}",
            f"[bold]Total Records:[/bold] {total_records:,}",
            f"[bold]Total Size:[/bold] {total_bytes / (1024**3):.2f} GB",
        ]

        # Add summary info if available
        if version.summary:
            lines.append("")
            lines.append("[bold]Operation Details:[/bold]")
            for key, value in version.summary.items():
                if key.startswith("metric_") or key.startswith("param_"):
                    display_key = (
                        key.replace("metric_", "").replace("param_", "").replace("_", " ").title()
                    )
                    lines.append(f"  {display_key}: {value}")

        content = "\n".join(lines)

        # Update content
        detail_content = self.query_one("#detail-content", Static)
        detail_content.update(content)

    def clear(self) -> None:
        """Clear the version details."""
        self._version = None
        detail_content = self.query_one("#detail-content", Static)
        detail_content.update("Select a version to view details")


class VersionFilesView(Container):
    """Widget for displaying files within a version."""

    DEFAULT_CSS = """
    VersionFilesView {
        height: 100%;
        overflow-y: auto;
    }

    VersionFilesView > DataTable {
        height: 100%;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the files view."""
        super().__init__(name=name, id=id, classes=classes)
        self._version: SnapshotInfo | None = None

    def compose(self) -> ComposeResult:
        """Compose the files view."""
        yield DataTable(id="files-table", cursor_type="row")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        table = self.query_one("#files-table", DataTable)
        table.add_columns("Path", "Size", "Records", "Partition")

        # If version was set before mount, update now
        if self._version:
            logger.debug(
                f"Version was set before mount, updating with {len(self._version.data_files)} files"
            )
            self._populate_table()

    def update_version(self, version: SnapshotInfo) -> None:
        """Update the displayed files.

        Args:
            version: SnapshotInfo containing files
        """
        self._version = version
        self._populate_table()

    def _populate_table(self) -> None:
        """Populate the table with files from current version."""
        if not self._version:
            return

        try:
            table = self.query_one("#files-table", DataTable)
            table.clear(columns=False)

            for file_ref in self._version.data_files:
                # Format size
                size_mb = file_ref.file_size_bytes / (1024**2)
                size_str = f"{size_mb:.2f} MB"

                # Format records
                records_str = f"{file_ref.record_count:,}" if file_ref.record_count else "N/A"

                # Format partition
                partition_str = ""
                if file_ref.partition:
                    partition_str = ", ".join(f"{k}={v}" for k, v in file_ref.partition.items())

                # Get filename from path
                filename = file_ref.path.split("/")[-1] if "/" in file_ref.path else file_ref.path

                table.add_row(filename, size_str, records_str, partition_str or "N/A")
        except Exception as e:
            logger.error(f"Error populating files table: {e}", exc_info=True)

    def clear(self) -> None:
        """Clear the files view."""
        self._version = None
        table = self.query_one("#files-table", DataTable)
        table.clear(columns=False)


class VersionSchemaView(Container):
    """Widget for displaying version schema."""

    DEFAULT_CSS = """
    VersionSchemaView {
        height: 100%;
        overflow-y: auto;
    }

    VersionSchemaView > DataTable {
        height: 100%;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the schema view."""
        super().__init__(name=name, id=id, classes=classes)
        self._schema: dict[str, str] | None = None

    def compose(self) -> ComposeResult:
        """Compose the schema view."""
        yield DataTable(id="schema-table", cursor_type="row")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        table = self.query_one("#schema-table", DataTable)
        table.add_columns("Column Name", "Data Type")

        if self._schema:
            self.update_schema(self._schema)

    def update_schema(self, schema: dict[str, str]) -> None:
        """Update the displayed schema.

        Args:
            schema: Dictionary mapping column names to types
        """
        try:
            table = self.query_one("#schema-table", DataTable)

            # Only skip update if schema unchanged AND table is already populated
            # This handles the case where on_mount() calls update_schema(self._schema)
            # with the same object reference on first mount
            if self._schema == schema and table.row_count > 0:
                return

            self._schema = schema

            # Clear existing rows (preserve columns)
            table.clear(columns=False)

            # Add schema fields
            for col_name, col_type in schema.items():
                table.add_row(col_name, col_type)

        except Exception as e:
            logger.error(f"Error updating schema view: {e}", exc_info=True)
            raise

    def clear(self) -> None:
        """Clear the schema view."""
        self._schema = None
        table = self.query_one("#schema-table", DataTable)
        table.clear(columns=False)


class VersionComparisonView(Container):
    """Widget for displaying version comparison."""

    DEFAULT_CSS = """
    VersionComparisonView {
        height: 100%;
        padding: 1;
        overflow-y: auto;
    }

    VersionComparisonView > Static {
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the comparison view."""
        super().__init__(name=name, id=id, classes=classes)

    def compose(self) -> ComposeResult:
        """Compose the comparison view."""
        yield Static("Select exactly 2 versions in Compare Mode", id="comparison-content")

    def update_comparison(self, version_a: SnapshotInfo, version_b: SnapshotInfo) -> None:
        """Update the comparison display.

        Args:
            version_a: First version
            version_b: Second version
        """
        lines = []
        lines.append("[bold cyan]Comparing Versions[/bold cyan]")
        lines.append(f"  Version A: {version_a.snapshot_id}")
        lines.append(f"  Version B: {version_b.snapshot_id}")
        lines.append("")

        # File changes
        files_a = len(version_a.data_files)
        files_b = len(version_b.data_files)
        files_delta = files_b - files_a

        lines.append("[bold cyan]File Changes[/bold cyan]")
        lines.append(f"  Version A Files: {files_a:,}")
        lines.append(f"  Version B Files: {files_b:,}")
        lines.append(f"  Delta: {files_delta:+,}")
        lines.append("")

        # Record changes
        records_a = sum(f.record_count for f in version_a.data_files if f.record_count is not None)
        records_b = sum(f.record_count for f in version_b.data_files if f.record_count is not None)
        records_delta = records_b - records_a

        lines.append("[bold cyan]Record Changes[/bold cyan]")
        lines.append(f"  Version A Records: {records_a:,}")
        lines.append(f"  Version B Records: {records_b:,}")
        lines.append(f"  Delta: {records_delta:+,}")
        lines.append("")

        # Size changes
        size_a = sum(f.file_size_bytes for f in version_a.data_files)
        size_b = sum(f.file_size_bytes for f in version_b.data_files)
        size_delta = size_b - size_a

        lines.append("[bold cyan]Size Changes[/bold cyan]")
        lines.append(f"  Version A Size: {size_a / (1024**3):.2f} GB")
        lines.append(f"  Version B Size: {size_b / (1024**3):.2f} GB")
        lines.append(f"  Delta: {size_delta / (1024**3):+.2f} GB")

        content = "\n".join(lines)
        comparison_content = self.query_one("#comparison-content", Static)
        comparison_content.update(content)

    def clear(self) -> None:
        """Clear the comparison view."""
        comparison_content = self.query_one("#comparison-content", Static)
        comparison_content.update("Select exactly 2 versions in Compare Mode")


class ForensicsView(Container):
    """Widget for displaying forensic analysis results."""

    DEFAULT_CSS = """
    ForensicsView {
        height: 100%;
        padding: 1;
        overflow-y: auto;
    }

    ForensicsView > Static {
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the forensics view."""
        super().__init__(name=name, id=id, classes=classes)

    def compose(self) -> ComposeResult:
        """Compose the forensics view."""
        yield Static("Loading forensic analysis...", id="forensics-content")

    def update_analysis(
        self,
        file_analysis: dict,
        storage_analysis: dict | None,
        checkpoint_health: dict | None,
    ) -> None:
        """Update the forensic analysis display.

        Args:
            file_analysis: File size analysis results
            storage_analysis: Storage waste analysis results (optional)
            checkpoint_health: Checkpoint health analysis results (optional)
        """
        lines = []

        # File Size Analysis
        lines.append("[bold cyan]File Size Distribution[/bold cyan]")
        lines.append("")
        lines.append(f"Total Files: {file_analysis['total_file_count']}")
        lines.append(f"Total Size: {file_analysis['total_size_bytes'] / (1024**3):.2f} GB")
        lines.append(f"Median Size: {file_analysis['median_size_bytes'] / (1024**2):.2f} MB")
        lines.append("")
        lines.append("Distribution:")
        for bucket, count in file_analysis["histogram"].items():
            percentage = (
                (count / file_analysis["total_file_count"] * 100)
                if file_analysis["total_file_count"] > 0
                else 0
            )
            lines.append(f"  {bucket}: {count} files ({percentage:.1f}%)")
        lines.append("")

        # Small File Analysis
        if file_analysis["small_file_percentage"] > 0:
            lines.append(
                f"[bold yellow]Small Files (<10MB):[/bold yellow] {file_analysis['small_file_count']} ({file_analysis['small_file_percentage']:.1f}%)"
            )
            if file_analysis["optimization_opportunity"] > 0:
                lines.append(
                    f"  Optimization could reduce by ~{file_analysis['optimization_opportunity']} files"
                )
            lines.append("")

        # Storage Waste Analysis
        if storage_analysis:
            lines.append("[bold cyan]Storage Waste Analysis[/bold cyan]")
            lines.append("")
            lines.append(f"Active Files: {storage_analysis['active_files']['count']}")
            lines.append(
                f"Active Size: {storage_analysis['active_files']['total_size_bytes'] / (1024**3):.2f} GB"
            )
            lines.append("")
            lines.append(f"Tombstone Files: {storage_analysis['tombstone_files']['count']}")
            lines.append(
                f"Tombstone Size: {storage_analysis['tombstone_files']['total_size_bytes'] / (1024**3):.2f} GB"
            )
            lines.append(f"Waste Percentage: {storage_analysis['waste_percentage']:.1f}%")
            lines.append("")
            if storage_analysis["reclaimable_bytes"] > 0:
                lines.append(
                    f"[bold yellow]Reclaimable:[/bold yellow] {storage_analysis['reclaimable_bytes'] / (1024**3):.2f} GB"
                )
                lines.append(f"  (beyond {storage_analysis['retention_period_hours']}h retention)")
            lines.append("")

        # Checkpoint Health
        if checkpoint_health:
            lines.append("[bold cyan]Checkpoint Health[/bold cyan]")
            lines.append("")
            status_color = {
                "healthy": "green",
                "degraded": "yellow",
                "critical": "red",
            }.get(checkpoint_health["health_status"], "white")
            lines.append(
                f"Status: [bold {status_color}]{checkpoint_health['health_status'].upper()}[/bold {status_color}]"
            )

            if checkpoint_health["last_checkpoint_version"] is not None:
                lines.append(
                    f"Last Checkpoint: Version {checkpoint_health['last_checkpoint_version']}"
                )
            else:
                lines.append("Last Checkpoint: None")

            lines.append(f"Log Tail Length: {checkpoint_health['log_tail_length']} files")

            if checkpoint_health["issues"]:
                lines.append("")
                lines.append("[bold yellow]Issues:[/bold yellow]")
                for issue in checkpoint_health["issues"]:
                    lines.append(f"  • {issue}")

            if checkpoint_health["recommendation"]:
                lines.append("")
                lines.append(f"[bold]Recommendation:[/bold] {checkpoint_health['recommendation']}")

        content = "\n".join(lines)
        forensics_content = self.query_one("#forensics-content", Static)
        forensics_content.update(content)

    def clear(self) -> None:
        """Clear the forensics view."""
        forensics_content = self.query_one("#forensics-content", Static)
        forensics_content.update("Loading forensic analysis...")


class RecommendationsView(Container):
    """Widget for displaying optimization recommendations."""

    DEFAULT_CSS = """
    RecommendationsView {
        height: 100%;
        padding: 1;
        overflow-y: auto;
    }

    RecommendationsView > Static {
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the recommendations view."""
        super().__init__(name=name, id=id, classes=classes)

    def compose(self) -> ComposeResult:
        """Compose the recommendations view."""
        yield Static("Loading recommendations...", id="recommendations-content")

    def update_recommendations(self, recommendations: list[dict]) -> None:
        """Update the recommendations display.

        Args:
            recommendations: List of recommendation dictionaries
        """
        if not recommendations:
            content = "[bold green]No optimization recommendations at this time.[/bold green]\n\nYour table appears to be well-optimized!"
        else:
            lines = []
            lines.append(f"[bold]Found {len(recommendations)} Recommendation(s)[/bold]")
            lines.append("")

            for i, rec in enumerate(recommendations, 1):
                # Priority color
                priority_color = {
                    "high": "red",
                    "medium": "yellow",
                    "low": "cyan",
                }.get(rec["priority"], "white")

                lines.append(
                    f"[bold {priority_color}]{i}. {rec['type']} (Priority: {rec['priority'].upper()})[/bold {priority_color}]"
                )
                lines.append(f"   Reason: {rec['reason']}")
                lines.append(f"   Impact: {rec['estimated_impact']}")
                lines.append(f"   Command: [italic]{rec['command']}[/italic]")
                lines.append("")

            content = "\n".join(lines)

        recommendations_content = self.query_one("#recommendations-content", Static)
        recommendations_content.update(content)

    def clear(self) -> None:
        """Clear the recommendations view."""
        recommendations_content = self.query_one("#recommendations-content", Static)
        recommendations_content.update("Loading recommendations...")


class DeltaView(Screen):
    """Screen for viewing Delta Lake table analysis.

    Provides:
    - Version history list (left panel)
    - Version details and forensic analysis (right panel with tabs)
    - Version comparison mode
    """

    TITLE = "Table Sleuth - Delta Lake Analysis"

    CSS = """
    DeltaView {
        layout: horizontal;
    }

    #left-panel {
        width: 40%;
        height: 100%;
        layout: vertical;
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
        ("escape", "dismiss_notification", "Dismiss"),
    ]

    def __init__(
        self,
        table_handle: TableHandle,
        adapter: DeltaAdapter,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the Delta viewer screen.

        Args:
            table_handle: Delta table handle
            adapter: Delta adapter instance
            name: Screen name
            id: Screen ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._table_handle = table_handle
        self._adapter = adapter

        # State
        self._versions: list[SnapshotInfo] = []
        self._selected_version: SnapshotInfo | None = None
        self._current_snapshot: SnapshotInfo | None = None
        self._compare_mode = False
        self._selected_versions: list[SnapshotInfo] = []

    def compose(self) -> ComposeResult:
        """Compose the Delta viewer screen."""
        yield Header()
        yield Notification(id="notification")
        yield LoadingIndicator(id="loading")

        with Horizontal():
            # Left panel: Version list
            with Vertical(id="left-panel"):
                # Table info header
                yield Static(self._format_table_info(), id="table-info")

                # Compare mode controls
                with Container(id="compare-controls"):
                    yield Checkbox("Compare Mode", id="compare-checkbox")

                # Version list
                yield VersionListView(id="version-list")

            # Right panel: Tabbed detail views
            with Vertical(id="right-panel"):
                with TabbedContent(id="detail-tabs"):
                    with TabPane("Overview", id="overview-tab"):
                        yield VersionDetailView(id="version-detail")

                    with TabPane("Files", id="files-tab"):
                        yield VersionFilesView(id="files-view")

                    with TabPane("Schema", id="schema-tab"):
                        yield VersionSchemaView(id="schema-view")

                    with TabPane("Data Sample", id="data-sample-tab"):
                        yield DataSampleView(id="data-sample-view")

                    with TabPane("Forensics", id="forensics-tab"):
                        yield ForensicsView(id="forensics-view")

                    with TabPane("Recommendations", id="recommendations-tab"):
                        yield RecommendationsView(id="recommendations-view")

                    with TabPane("Compare", id="compare-tab", disabled=True):
                        yield VersionComparisonView(id="comparison-view")

        yield Footer()

    def on_mount(self) -> None:
        """Set up the screen when mounted."""
        # Load versions
        self._load_versions()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle compare mode checkbox change.

        Args:
            event: Checkbox change event
        """
        if event.checkbox.id == "compare-checkbox":
            self._compare_mode = event.value
            self._selected_versions = []

            # Update UI
            notification = self.query_one("#notification", Notification)
            if self._compare_mode:
                notification.info("Compare mode enabled. Select 2 versions to compare.")
            else:
                notification.info("Compare mode disabled.")
                # Disable compare tab
                compare_tab = self.query_one("#compare-tab", TabPane)
                compare_tab.disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle version selection in the list.

        Args:
            event: Row selection event
        """
        # Get the selected version
        version_list = self.query_one("#version-list", VersionListView)
        selected_version = version_list.get_selected_version()

        if selected_version:
            if self._compare_mode:
                # In compare mode, track multiple selections
                if selected_version not in self._selected_versions:
                    self._selected_versions.append(selected_version)

                    # Limit to 2 versions
                    if len(self._selected_versions) > 2:
                        self._selected_versions.pop(0)

                    # Update compare mode UI
                    if len(self._selected_versions) == 2:
                        self._update_comparison()
            else:
                # Normal mode: single selection
                self._selected_version = selected_version
                self._load_version_details(selected_version)

    def _format_table_info(self) -> str:
        """Format table information for display.

        Returns:
            Formatted table info string
        """
        dt = self._table_handle.native
        lines = [
            f"[bold]Table:[/bold] {dt.table_uri}",
            f"[bold]Current Version:[/bold] {dt.version()}",
        ]
        return "\n".join(lines)

    def _load_versions(self) -> None:
        """Load version history from the table."""
        loading = self.query_one("#loading", LoadingIndicator)
        loading.show("Loading version history...")

        try:
            # Load all versions
            self._versions = self._adapter.list_snapshots(self._table_handle)

            # Get versions with metaData entries (schema changes)
            versions_with_metadata = self._adapter.get_versions_with_metadata(self._table_handle)

            # Update version list view
            version_list = self.query_one("#version-list", VersionListView)
            version_list.set_versions_with_metadata(versions_with_metadata)
            version_list.update_versions(self._versions)

            # Load current version
            if self._versions:
                self._current_snapshot = self._versions[-1]  # Latest version

            # Show success notification
            notification = self.query_one("#notification", Notification)
            notification.success(f"Loaded {len(self._versions)} versions")

            # Run forensic analysis on current version
            if self._current_snapshot:
                self._run_forensic_analysis(self._current_snapshot)

        except Exception as e:
            logger.exception("Failed to load versions")
            notification = self.query_one("#notification", Notification)
            notification.error(f"Failed to load versions: {e}")

        finally:
            loading.hide()

    def _load_version_details(self, version: SnapshotInfo) -> None:
        """Load detailed information for a version.

        Args:
            version: Version to load details for
        """
        loading = self.query_one("#loading", LoadingIndicator)
        loading.show(f"Loading version {version.snapshot_id}...")

        try:
            # Update version detail view
            version_detail = self.query_one("#version-detail", VersionDetailView)
            version_detail.update_version(version)

            # Update files view
            files_view = self.query_one("#files-view", VersionFilesView)
            files_view.update_version(version)

            # Update schema view
            schema = self._adapter.get_schema_at_version(self._table_handle, version.snapshot_id)
            schema_view = self.query_one("#schema-view", VersionSchemaView)
            schema_view.update_schema(schema)

            # Update data sample view with first file
            data_sample = self.query_one("#data-sample-view", DataSampleView)
            if version.data_files:
                from tablesleuth.services.parquet_service import ParquetInspector

                first_file = version.data_files[0]
                file_path = first_file.path

                try:
                    # Get AWS region from adapter's storage options if available
                    region = (
                        self._adapter.storage_options.get("AWS_REGION")
                        if self._adapter.storage_options
                        else None
                    )

                    # Create inspector with region
                    parquet_inspector = ParquetInspector(region=region)
                    file_info = parquet_inspector.inspect_file(file_path)

                    # Pass region to data sample view for S3 file access
                    data_sample.update_file_info(file_info, region=region)

                except Exception as e:
                    logger.warning(f"Failed to load data sample: {e}", exc_info=True)
                    data_sample.clear()
            else:
                data_sample.clear()

        except Exception as e:
            logger.exception(f"Failed to load version details: {e}")
            notification = self.query_one("#notification", Notification)
            notification.error(f"Failed to load version details: {e}")

        finally:
            loading.hide()

    def _update_comparison(self) -> None:
        """Update comparison view with selected versions."""
        if len(self._selected_versions) != 2:
            return

        loading = self.query_one("#loading", LoadingIndicator)
        loading.show("Comparing versions...")

        try:
            version_a, version_b = self._selected_versions

            # Enable compare tab
            compare_tab = self.query_one("#compare-tab", TabPane)
            compare_tab.disabled = False

            # Update comparison view
            comparison_view = self.query_one("#comparison-view", VersionComparisonView)
            comparison_view.update_comparison(version_a, version_b)

            # Show success notification
            notification = self.query_one("#notification", Notification)
            notification.success(
                f"Comparing versions {version_a.snapshot_id} and {version_b.snapshot_id}"
            )

        except Exception as e:
            logger.exception("Failed to compare versions")
            notification = self.query_one("#notification", Notification)
            notification.error(f"Failed to compare versions: {e}")

        finally:
            loading.hide()

    def _run_forensic_analysis(self, snapshot: SnapshotInfo) -> None:
        """Run forensic analysis on the current snapshot.

        Args:
            snapshot: Snapshot to analyze
        """
        loading = self.query_one("#loading", LoadingIndicator)
        loading.show("Running forensic analysis...")

        try:
            dt = self._table_handle.native
            storage_options = self._adapter.storage_options

            # File size analysis
            file_analysis = DeltaForensics.analyze_file_sizes(snapshot)

            # Storage waste analysis
            try:
                storage_analysis = DeltaForensics.analyze_storage_waste(
                    dt, dt.version(), storage_options=storage_options
                )
            except Exception as e:
                logger.warning(f"Storage waste analysis failed: {e}")
                storage_analysis = None

            # Checkpoint health
            try:
                checkpoint_health = DeltaForensics.analyze_checkpoint_health(
                    dt, storage_options=storage_options
                )
            except Exception as e:
                logger.warning(f"Checkpoint health analysis failed: {e}")
                checkpoint_health = None

            # Update forensics view
            forensics_view = self.query_one("#forensics-view", ForensicsView)
            forensics_view.update_analysis(file_analysis, storage_analysis, checkpoint_health)

            # Generate recommendations
            try:
                recommendations = DeltaForensics.generate_recommendations(
                    dt, snapshot, storage_options=storage_options
                )
                recommendations_view = self.query_one("#recommendations-view", RecommendationsView)
                recommendations_view.update_recommendations(recommendations)
            except Exception as e:
                logger.warning(f"Failed to generate recommendations: {e}")

        except Exception as e:
            logger.exception("Failed to run forensic analysis")
            notification = self.query_one("#notification", Notification)
            notification.error(f"Forensic analysis failed: {e}")

        finally:
            loading.hide()

    def action_refresh(self) -> None:
        """Refresh the version list and analysis."""
        self._load_versions()

    def action_toggle_compare(self) -> None:
        """Toggle compare mode."""
        checkbox = self.query_one("#compare-checkbox", Checkbox)
        checkbox.toggle()

    def action_dismiss_notification(self) -> None:
        """Dismiss the notification."""
        notification = self.query_one("#notification", Notification)
        notification.dismiss()

    def action_quit(self) -> None:
        """Quit the screen."""
        self.app.exit()
