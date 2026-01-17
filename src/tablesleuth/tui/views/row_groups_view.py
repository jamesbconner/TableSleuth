"""Row groups view widget for displaying Parquet row group information."""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Collapsible, Static

from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo


class RowGroupsView(Container):
    """Widget for displaying Parquet row group information.

    Displays row groups with:
    - Row group index
    - Row count per group
    - Total size per group
    - Expandable column-level statistics
    """

    DEFAULT_CSS = """
    RowGroupsView {
        height: 100%;
        border: solid $primary;
        overflow-y: auto;
    }

    RowGroupsView > Static#rowgroups-header {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    RowGroupsView > Vertical {
        height: auto;
        padding: 1;
    }

    RowGroupsView Collapsible {
        margin-bottom: 1;
        border: solid $accent;
    }

    RowGroupsView .rg-summary {
        color: $text;
    }

    RowGroupsView .rg-details {
        padding: 1;
        color: $text-muted;
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
        """Initialize the row groups view.

        Args:
            file_info: Optional ParquetFileInfo to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._file_info = file_info

    def compose(self) -> ComposeResult:
        """Compose the row groups view."""
        yield Static("Row Groups", id="rowgroups-header")
        yield Vertical(
            Static("No file selected", id="rowgroups-content"),
            id="rowgroups-container",
        )

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        if self._file_info:
            self.update_row_groups(self._file_info)

    def update_row_groups(self, file_info: ParquetFileInfo) -> None:
        """Update the displayed row groups.

        Args:
            file_info: ParquetFileInfo with row group information
        """
        self._file_info = file_info

        # Update header
        header = self.query_one("#rowgroups-header", Static)
        header.update(f"Row Groups ({file_info.num_row_groups})")

        # Clear existing content
        container = self.query_one("#rowgroups-container", Vertical)
        container.remove_children()

        # Add collapsible for each row group
        for rg in file_info.row_groups:
            # Create summary text
            size_str = self._format_size(rg.total_byte_size)
            summary = f"Group {rg.index}: {rg.num_rows:,} rows, {size_str}"

            # Create details content with Rich panels
            # Create column panels in a grid layout (3 columns)
            col_table = Table.grid(padding=(0, 1), expand=True)
            col_table.add_column(ratio=1)
            col_table.add_column(ratio=1)
            col_table.add_column(ratio=1)

            # Build rows of column panels
            cols_per_row = 3
            num_cols = len(rg.columns)

            for row_idx in range(0, num_cols, cols_per_row):
                row_panels: list[Panel | Text] = []
                for col_offset in range(cols_per_row):
                    col_idx = row_idx + col_offset
                    if col_idx < num_cols:
                        col = rg.columns[col_idx]
                        col_panel = self._create_column_panel(col)
                        row_panels.append(col_panel)
                    else:
                        # Empty space for alignment
                        row_panels.append(Text(""))

                col_table.add_row(*row_panels)

            # Create collapsible widget
            collapsible = Collapsible(
                Static(col_table, classes="rg-details"),
                title=summary,
                collapsed=True,
            )

            container.mount(collapsible)

    def clear(self) -> None:
        """Clear the row groups view."""
        self._file_info = None

        # Update header
        header = self.query_one("#rowgroups-header", Static)
        header.update("Row Groups")

        # Clear content
        container = self.query_one("#rowgroups-container", Vertical)
        container.remove_children()
        container.mount(Static("No file selected", id="rowgroups-content"))

    def _create_column_panel(self, col: ColumnStats) -> Panel:
        """Create a Rich Panel for a column with enhanced statistics.

        Args:
            col: Column statistics object

        Returns:
            Rich Panel with column details
        """
        col_text = Text()

        # Type
        col_text.append("Type: ", style="dim")
        col_text.append(f"{col.physical_type}\n", style="cyan")

        # Codec
        col_text.append("Codec: ", style="dim")
        codec_style = "green" if col.compression != "UNCOMPRESSED" else "yellow"
        col_text.append(f"{col.compression}\n", style=codec_style)

        # Values
        col_text.append("Values: ", style="dim")
        if col.num_values is not None:
            col_text.append(f"{col.num_values:,}\n")
        else:
            col_text.append("N/A\n", style="dim")

        # Nulls
        col_text.append("Nulls: ", style="dim")
        if col.null_count is not None:
            null_style = "red" if col.null_count > 0 else "green"
            col_text.append(f"{col.null_count:,}\n", style=null_style)
        else:
            col_text.append("N/A\n", style="dim")

        # Distinct count
        col_text.append("Distinct: ", style="dim")
        if col.distinct_count is not None:
            col_text.append(f"{col.distinct_count:,}\n")
        else:
            col_text.append("N/A\n", style="dim")

        # Sizes and compression ratio
        if col.total_compressed_size is not None and col.total_uncompressed_size is not None:
            col_text.append("Compressed: ", style="dim")
            col_text.append(f"{self._format_size(col.total_compressed_size)}\n")

            col_text.append("Uncompressed: ", style="dim")
            col_text.append(f"{self._format_size(col.total_uncompressed_size)}\n")

            ratio, ratio_color = self._calculate_compression_ratio(
                col.total_compressed_size, col.total_uncompressed_size
            )
            if ratio is not None:
                col_text.append("Ratio: ", style="dim")
                col_text.append(f"{ratio:.1f}%\n", style=ratio_color)

        # Min/Max values
        if col.min_value is not None and col.max_value is not None:
            min_str = str(col.min_value)[:25]
            max_str = str(col.max_value)[:25]
            col_text.append("Min: ", style="dim")
            col_text.append(f"{min_str}\n", style="green")
            col_text.append("Max: ", style="dim")
            col_text.append(f"{max_str}", style="green")
        elif col.num_values is None and col.null_count is None:
            # If most stats are missing, show single message
            col_text.append("Stats: ", style="dim")
            col_text.append("Not available", style="yellow")

        return Panel(
            col_text,
            title=f"[bold cyan]{col.name}[/bold cyan]",
            border_style="dim",
            padding=(0, 1),
        )

    @staticmethod
    def _format_size(size_bytes: int | None) -> str:
        """Format size in human-readable format.

        Args:
            size_bytes: Size in bytes (None if unavailable)

        Returns:
            Formatted size string (e.g., "1.2 MB") or "N/A"
        """
        if size_bytes is None:
            return "N/A"

        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    @staticmethod
    def _calculate_compression_ratio(
        compressed: int | None, uncompressed: int | None
    ) -> tuple[float | None, str]:
        """Calculate compression ratio and determine color.

        Args:
            compressed: Compressed size in bytes
            uncompressed: Uncompressed size in bytes

        Returns:
            Tuple of (ratio as percentage, color style)
        """
        if compressed is None or uncompressed is None or uncompressed == 0:
            return None, "dim"

        ratio = (compressed / uncompressed) * 100
        color = "green" if ratio < 50 else "yellow"
        return ratio, color
