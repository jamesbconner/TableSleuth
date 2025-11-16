"""Column statistics view widget for displaying Parquet column metadata."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static

from table_sleuth.models.parquet import ColumnStats


class ColumnStatsView(Container):
    """Widget for displaying Parquet column statistics.

    Displays column statistics from Parquet metadata:
    - Null count
    - Min/max values
    - Encoding types
    - Compression codec

    Handles missing statistics gracefully by showing "N/A".
    Updates when a column is selected in the schema view.
    """

    DEFAULT_CSS = """
    ColumnStatsView {
        height: 100%;
        border: solid $primary;
        overflow-y: auto;
    }

    ColumnStatsView > Static#colstats-header {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    ColumnStatsView > Vertical {
        height: auto;
        padding: 1;
    }

    ColumnStatsView .stats-content {
        color: $text;
        padding: 0 1;
    }

    ColumnStatsView .stats-label {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        column_stats: ColumnStats | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the column stats view.

        Args:
            column_stats: Optional ColumnStats to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._column_stats = column_stats

    def compose(self) -> ComposeResult:
        """Compose the column stats view."""
        yield Static("Column Statistics", id="colstats-header")
        yield Vertical(
            Static("No column selected", id="colstats-content", classes="stats-content"),
            id="colstats-container",
        )

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        if self._column_stats:
            self.update_column_stats(self._column_stats)

    def update_column_stats(self, column_stats: ColumnStats) -> None:
        """Update the displayed column statistics.

        Args:
            column_stats: ColumnStats with column metadata
        """
        self._column_stats = column_stats

        # Update header with column name
        header = self.query_one("#colstats-header", Static)
        header.update(f"Column Statistics: {column_stats.name}")

        # Build statistics content
        lines = []

        # Column type information
        lines.append("[bold]Type Information[/bold]")
        lines.append(f"  Physical Type: {column_stats.physical_type}")
        logical_type = column_stats.logical_type or "N/A"
        lines.append(f"  Logical Type: {logical_type}")
        lines.append("")

        # Statistics from metadata
        lines.append("[bold]Statistics[/bold]")

        # Null count
        if column_stats.null_count is not None:
            lines.append(f"  Null Count: {column_stats.null_count:,}")
        else:
            lines.append("  Null Count: N/A")

        # Min value
        if column_stats.min_value is not None:
            min_str = self._format_value(column_stats.min_value)
            lines.append(f"  Min Value: {min_str}")
        else:
            lines.append("  Min Value: N/A")

        # Max value
        if column_stats.max_value is not None:
            max_str = self._format_value(column_stats.max_value)
            lines.append(f"  Max Value: {max_str}")
        else:
            lines.append("  Max Value: N/A")

        lines.append("")

        # Encoding and compression
        lines.append("[bold]Storage[/bold]")

        # Encodings
        if column_stats.encodings:
            encodings_str = ", ".join(column_stats.encodings)
            lines.append(f"  Encodings: {encodings_str}")
        else:
            lines.append("  Encodings: N/A")

        # Compression
        lines.append(f"  Compression: {column_stats.compression}")

        # Update content
        content = self.query_one("#colstats-content", Static)
        content.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the column stats view."""
        self._column_stats = None

        # Update header
        header = self.query_one("#colstats-header", Static)
        header.update("Column Statistics")

        # Clear content
        content = self.query_one("#colstats-content", Static)
        content.update("No column selected")

    @staticmethod
    def _format_value(value: object) -> str:
        """Format a value for display.

        Truncates long values and handles special types.

        Args:
            value: Value to format

        Returns:
            Formatted string representation
        """
        # Convert to string
        value_str = str(value)

        # Truncate if too long
        max_length = 50
        if len(value_str) > max_length:
            return value_str[:max_length] + "..."

        return value_str
