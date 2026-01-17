"""Profile view widget for displaying column profiling results."""

from __future__ import annotations

import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Input, Static

from tablesleuth.models.parquet import ParquetFileInfo
from tablesleuth.models.profiling import ColumnProfile

logger = logging.getLogger(__name__)


class ProfileColumnRequested(Message):
    """Message requesting column profiling."""

    def __init__(self, column_name: str) -> None:
        """Initialize message.

        Args:
            column_name: Name of column to profile
        """
        super().__init__()
        self.column_name = column_name


class ProfileView(Container):
    """Widget for displaying column profiling results.

    Features:
    - Filterable column list (left panel)
    - Click to profile any column
    - Rich-formatted results (right panel)
    - Comprehensive statistics including quartiles, mode, IQR
    - Independent operation (no Schema view dependency)
    """

    DEFAULT_CSS = """
    ProfileView {
        height: 100%;
        border: solid $primary;
    }

    ProfileView > Static#profile-header {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    ProfileView #profile-content {
        height: 1fr;
    }

    ProfileView #profile-column-selector {
        width: 40%;
        border-right: solid $accent;
        padding: 1;
    }

    ProfileView #profile-results-container {
        width: 60%;
        padding: 1;
    }

    ProfileView .selector-label {
        margin-top: 1;
        margin-bottom: 0;
        text-style: bold;
    }

    ProfileView Input {
        width: 100%;
        margin-bottom: 1;
    }

    ProfileView #column-list-scroll {
        height: 1fr;
    }

    ProfileView .column-item {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    ProfileView .column-item.selected {
        color: $success;
        background: $accent;
    }

    ProfileView .column-item:hover {
        background: $accent;
    }

    ProfileView #profile-results {
        padding: 1;
    }
    """

    def __init__(
        self,
        file_info: ParquetFileInfo | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the profile view.

        Args:
            file_info: Optional ParquetFileInfo to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._file_info = file_info
        self._selected_column: str | None = None
        self._column_filter = ""
        self._profile_result: ColumnProfile | None = None
        self._is_loading = False

    def compose(self) -> ComposeResult:
        """Compose the profile view."""
        yield Static("Profile", id="profile-header")

        with Horizontal(id="profile-content"):
            # Left side: Column selector (40%)
            with VerticalScroll(id="profile-column-selector"):
                yield Static("Filter Columns:", classes="selector-label")
                yield Input(placeholder="Type to filter...", id="column-filter")
                yield Static("Columns:", classes="selector-label")
                with VerticalScroll(id="column-list-scroll"):
                    yield Vertical(id="column-list")

            # Right side: Profile results (60%)
            with VerticalScroll(id="profile-results-container"):
                yield Static("Select a column to profile", id="profile-results")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes.

        Args:
            event: Input changed event
        """
        if event.input.id == "column-filter":
            self._column_filter = event.value.lower()
            self._update_column_list()

    def on_click(self, event: Any) -> None:
        """Handle clicks on column items.

        Args:
            event: Click event
        """
        # Check if click was on a column item
        if hasattr(event, "widget") and event.widget.has_class("column-item"):
            # Extract column name from label
            try:
                rendered = event.widget.render()
                label = str(rendered.plain) if hasattr(rendered, "plain") else str(rendered)
                col_name = label[2:] if label.startswith("✓ ") else label.strip()

                # Update selection
                self._selected_column = col_name
                self._update_column_list()  # Refresh to show new selection

                # Trigger profiling
                self._profile_column(col_name)

            except Exception as e:
                logger.error(f"Error handling column click: {e}")

    def update_file_info(self, file_info: ParquetFileInfo) -> None:
        """Update the displayed file information.

        Args:
            file_info: ParquetFileInfo with file metadata
        """
        self._file_info = file_info
        self._selected_column = None
        self._profile_result = None

        # Create column list
        self._create_column_list()

        # Show initial message
        results = self.query_one("#profile-results", Static)
        results.update("Select a column to profile")

    def clear(self) -> None:
        """Clear the profile view."""
        self._file_info = None
        self._selected_column = None
        self._column_filter = ""
        self._profile_result = None
        self._is_loading = False

        # Clear column list
        try:
            container = self.query_one("#column-list", Vertical)
            container.remove_children()
        except Exception as e:
            logger.debug(f"Could not clear column list: {e}")

        # Clear filter
        try:
            filter_input = self.query_one("#column-filter", Input)
            filter_input.value = ""
        except Exception as e:
            logger.debug(f"Could not clear filter input: {e}")

        # Show "No file loaded" message
        try:
            results = self.query_one("#profile-results", Static)
            results.update("No file loaded")
        except Exception as e:
            logger.debug(f"Could not update results: {e}")

    def _create_column_list(self) -> None:
        """Create clickable column list."""
        if self._file_info is None:
            logger.debug("No file_info available for creating column list")
            return

        try:
            container = self.query_one("#column-list", Vertical)
            container.remove_children()

            logger.debug(f"Creating column items for {len(self._file_info.columns)} columns")

            # Create Static widget for each column (NO IDs - avoids conflicts)
            for col in self._file_info.columns:
                is_selected = col.name == self._selected_column
                label = f"✓ {col.name}" if is_selected else f"  {col.name}"
                classes = "column-item selected" if is_selected else "column-item"

                item = Static(label, classes=classes)
                container.mount(item)
                logger.debug(f"Created item for column: {col.name}")
        except Exception as e:
            logger.error(f"Error creating column list: {e}")

    def _update_column_list(self) -> None:
        """Update column list based on filter."""
        if self._file_info is None:
            return

        try:
            container = self.query_one("#column-list", Vertical)

            # Remove all existing column items
            for item in list(container.query(".column-item")):
                item.remove()

            # Filter columns based on search text
            filtered_columns = [
                col for col in self._file_info.columns if self._column_filter in col.name.lower()
            ]

            logger.debug(
                f"Showing {len(filtered_columns)} of {len(self._file_info.columns)} columns"
            )

            # Create Static widget for each filtered column
            for col in filtered_columns:
                is_selected = col.name == self._selected_column
                label = f"✓ {col.name}" if is_selected else f"  {col.name}"
                classes = "column-item selected" if is_selected else "column-item"

                item = Static(label, classes=classes)
                container.mount(item)
        except Exception as e:
            logger.error(f"Error updating column list: {e}")

    def _profile_column(self, column_name: str) -> None:
        """Trigger profiling for a column.

        Args:
            column_name: Name of column to profile
        """
        # Show loading state
        self._show_loading(column_name)

        # Post message to app to trigger profiling
        # App will call GizmoSQL backend and then call update_profile()
        self.post_message(ProfileColumnRequested(column_name))

    def _show_loading(self, column_name: str) -> None:
        """Show loading indicator.

        Args:
            column_name: Name of column being profiled
        """
        self._is_loading = True

        content = f"[bold cyan]Profiling: {column_name}[/bold cyan]\n\n"
        content += "[yellow]⏳ Profiling in progress...[/yellow]\n\n"
        content += "This may take a few seconds for large columns."

        results = self.query_one("#profile-results", Static)
        results.update(content)

    def update_profile(self, profile: ColumnProfile) -> None:
        """Update the displayed profile results.

        Args:
            profile: ColumnProfile with profiling results
        """
        self._profile_result = profile
        self._is_loading = False

        # Build Rich panel with results
        content = self._build_profile_content(profile)

        # Update results container
        results = self.query_one("#profile-results", Static)
        results.update(content)

    def show_error(self, error_message: str) -> None:
        """Show error message.

        Args:
            error_message: Error message to display
        """
        self._is_loading = False

        content = "[bold red]Profiling Error[/bold red]\n\n"
        content += f"[red]{error_message}[/red]\n\n"
        content += "[dim]Please try selecting a different column.[/dim]"

        results = self.query_one("#profile-results", Static)
        results.update(content)

    def _build_profile_content(self, profile: ColumnProfile) -> str:
        """Build Rich-formatted profile content.

        Args:
            profile: ColumnProfile with results

        Returns:
            Rich markup string
        """
        lines = []

        # Header
        lines.append(f"[bold cyan]Column Profile: {profile.column}[/bold cyan]")
        lines.append("")

        # Row Statistics
        lines.append("[bold]Row Statistics[/bold]")
        lines.append(f"  Total Rows: [cyan]{profile.row_count:,}[/cyan]")
        lines.append(f"  Non-Null Rows: [cyan]{profile.non_null_count:,}[/cyan]")
        lines.append(f"  Null Rows: [red]{profile.null_count:,}[/red]")

        if profile.row_count > 0:
            null_pct = (profile.null_count / profile.row_count) * 100
            lines.append(f"  Null Percentage: [red]{null_pct:.2f}%[/red]")

        lines.append("")

        # Cardinality
        lines.append("[bold]Cardinality[/bold]")
        if profile.distinct_count is not None:
            lines.append(f"  Distinct Values: [cyan]{profile.distinct_count:,}[/cyan]")

            if profile.row_count > 0:
                cardinality_pct = (profile.distinct_count / profile.row_count) * 100
                lines.append(f"  Cardinality: [cyan]{cardinality_pct:.2f}%[/cyan]")
        else:
            lines.append("  Distinct Values: [dim]N/A[/dim]")

        lines.append("")

        # Mode (most frequent value)
        lines.append("[bold]Mode[/bold]")
        if profile.mode is not None:
            mode_str = self._format_value(profile.mode)
            lines.append(f"  Most Frequent: [yellow]{mode_str}[/yellow]")
            if profile.mode_count is not None:
                lines.append(f"  Frequency: [yellow]{profile.mode_count:,}[/yellow]")
        else:
            lines.append("  Most Frequent: [dim]N/A[/dim]")

        lines.append("")

        # Numeric Statistics (if applicable)
        if profile.is_numeric and profile.average is not None:
            lines.append("[bold]Numeric Statistics[/bold]")
            lines.append(f"  Average: [cyan]{profile.average:,.4f}[/cyan]")

            if profile.median is not None:
                lines.append(f"  Median (Q2): [cyan]{profile.median:,.4f}[/cyan]")

            if profile.std_dev is not None:
                lines.append(f"  Std Deviation: [cyan]{profile.std_dev:,.4f}[/cyan]")

            if profile.variance is not None:
                lines.append(f"  Variance: [cyan]{profile.variance:,.4f}[/cyan]")

            lines.append("")

            # Quartiles
            if profile.q1 is not None and profile.q3 is not None:
                lines.append("[bold]Quartiles[/bold]")
                lines.append(f"  Q1 (25th percentile): [cyan]{profile.q1:,.4f}[/cyan]")
                if profile.median is not None:
                    lines.append(f"  Q2 (50th percentile): [cyan]{profile.median:,.4f}[/cyan]")
                lines.append(f"  Q3 (75th percentile): [cyan]{profile.q3:,.4f}[/cyan]")

                # IQR
                iqr = profile.q3 - profile.q1
                lines.append(f"  IQR (Q3 - Q1): [cyan]{iqr:,.4f}[/cyan]")

                lines.append("")

        # Value Range
        lines.append("[bold]Value Range[/bold]")
        if profile.min_value is not None:
            min_str = self._format_value(profile.min_value)
            lines.append(f"  Min Value: [green]{min_str}[/green]")
        else:
            lines.append("  Min Value: [dim]N/A[/dim]")

        if profile.max_value is not None:
            max_str = self._format_value(profile.max_value)
            lines.append(f"  Max Value: [green]{max_str}[/green]")
        else:
            lines.append("  Max Value: [dim]N/A[/dim]")

        return "\n".join(lines)

    def _format_value(self, value: Any) -> str:
        """Format a value for display.

        Args:
            value: Value to format

        Returns:
            Formatted string
        """
        if value is None:
            return "NULL"

        if isinstance(value, int | float):
            if isinstance(value, float):
                return f"{value:,.4f}"
            return f"{value:,}"

        # Truncate long strings
        str_value = str(value)
        if len(str_value) > 50:
            return str_value[:47] + "..."

        return str_value

    @property
    def is_loading(self) -> bool:
        """Check if profiling is in progress.

        Returns:
            True if profiling is in progress
        """
        return self._is_loading
