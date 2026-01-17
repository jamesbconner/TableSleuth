"""Structure view widget for displaying Parquet file physical structure."""

from __future__ import annotations

import logging

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static

from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo

logger = logging.getLogger(__name__)


class StructureView(Container):
    """Widget for displaying Parquet file physical structure.

    Displays the internal file layout including:
    - File header with magic number
    - Row groups with column chunks
    - Page indexes (if available)
    - File footer with metadata
    """

    DEFAULT_CSS = """
    StructureView {
        height: 100%;
        overflow-y: auto;
    }

    #structure-content {
        height: auto;
    }

    .structure-section {
        height: auto;
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
        """Initialize the structure view.

        Args:
            file_info: Optional ParquetFileInfo to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._file_info = file_info
        self._content_container: Vertical | None = None

    def compose(self) -> ComposeResult:
        """Compose the structure view."""
        yield Vertical(
            Static("No file selected", id="structure-placeholder"),
            id="structure-content",
        )

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        try:
            self._content_container = self.query_one("#structure-content", Vertical)
            logger.debug(f"Structure view mounted, content_container: {self._content_container}")
            if self._file_info:
                logger.debug(f"Structure view has file_info on mount: {self._file_info.path}")
                self.update_structure(self._file_info)
        except Exception as e:
            logger.exception(f"Error in structure view on_mount: {e}")

    def update_structure(self, file_info: ParquetFileInfo) -> None:
        """Update the displayed structure information.

        Args:
            file_info: ParquetFileInfo object with file metadata
        """
        try:
            self._file_info = file_info
            logger.debug(f"Updating structure view with file: {file_info.path}")

            if self._content_container is None:
                logger.warning("Structure view content_container is None, attempting to query")
                try:
                    self._content_container = self.query_one("#structure-content", Vertical)
                    logger.debug("Successfully queried content_container")
                except Exception as e:
                    logger.error(f"Failed to query content_container: {e}")
                    return

            # Clear existing content
            self._content_container.remove_children()

            # Build structure display with error handling
            widgets: list[Static | Container] = []

            try:
                widgets.append(self._render_header(file_info))
            except Exception as e:
                logger.warning(f"Failed to render header: {e}")
                widgets.append(Static("[red]Error rendering header[/red]"))

            try:
                widgets.append(self._render_row_groups(file_info))
            except Exception as e:
                logger.warning(f"Failed to render row groups: {e}")
                widgets.append(Static("[red]Error rendering row groups[/red]"))

            try:
                widgets.append(self._render_page_indexes(file_info))
            except Exception as e:
                logger.warning(f"Failed to render page indexes: {e}")
                widgets.append(Static("[red]Error rendering page indexes[/red]"))

            try:
                widgets.append(self._render_footer(file_info))
            except Exception as e:
                logger.warning(f"Failed to render footer: {e}")
                widgets.append(Static("[red]Error rendering footer[/red]"))

            self._content_container.mount(*widgets)

        except Exception as e:
            logger.exception("Error updating structure view")
            if self._content_container:
                self._content_container.remove_children()
                self._content_container.mount(Static(f"[red]Error displaying structure: {e}[/red]"))

    def clear(self) -> None:
        """Clear the structure view."""
        self._file_info = None
        if self._content_container:
            self._content_container.remove_children()
            self._content_container.mount(Static("No file selected", id="structure-placeholder"))

    def _render_header(self, file_info: ParquetFileInfo) -> Static:
        """Render the file header section using Rich Panel.

        Args:
            file_info: ParquetFileInfo object

        Returns:
            Container with header information
        """
        header_text = Text()
        header_text.append("Magic Number: ", style="bold")
        header_text.append("PAR1\n", style="yellow")
        header_text.append("Size: ", style="bold")
        header_text.append("4 bytes")

        panel = Panel(
            header_text,
            title="[bold yellow]HEADER[/bold yellow]",
            border_style="yellow",
        )

        return Static(panel)

    def _render_row_groups(self, file_info: ParquetFileInfo) -> Container:
        """Render all row group sections using Rich Panels and Tables.

        Args:
            file_info: ParquetFileInfo object

        Returns:
            Container widget with all row groups
        """
        row_group_panels = []

        for rg in file_info.row_groups:
            # Row group summary
            summary = Text()
            summary.append("Rows: ", style="bold")
            summary.append(f"{rg.num_rows:,}\n")
            summary.append("Size: ", style="bold")
            summary.append(f"{self._format_size(rg.total_byte_size)}\n")
            summary.append("Columns: ", style="bold")
            summary.append(f"{len(rg.columns)}")

            # Create column chunks table (3 columns layout)
            col_table = Table.grid(padding=(0, 1), expand=True)
            col_table.add_column(ratio=1)
            col_table.add_column(ratio=1)
            col_table.add_column(ratio=1)

            # Build rows of column panels
            cols_per_row = 3
            max_cols_to_show = min(len(rg.columns), 15)  # Limit display

            for row_idx in range(0, max_cols_to_show, cols_per_row):
                row_panels: list[Panel | Text] = []
                for col_offset in range(cols_per_row):
                    col_idx = row_idx + col_offset
                    if col_idx < max_cols_to_show:
                        col = rg.columns[col_idx]
                        col_panel = self._create_column_panel(col)
                        row_panels.append(col_panel)
                    else:
                        # Empty space for alignment
                        row_panels.append(Text(""))

                col_table.add_row(*row_panels)

            # If too many columns, add note
            if len(rg.columns) > max_cols_to_show:
                remaining_text = Text()
                remaining_text.append(
                    f"... and {len(rg.columns) - max_cols_to_show} more columns",
                    style="dim italic",
                )
                col_table.add_row(Panel(remaining_text, border_style="dim"), Text(""), Text(""))

            # Combine summary and column table
            rg_content = Group(summary, Text(), col_table)

            panel = Panel(
                rg_content,
                title=f"[bold]Row Group {rg.index}[/bold]",
                border_style="dim",
            )

            row_group_panels.append(panel)

        # Combine all row groups into a single Group
        all_row_groups = Group(*row_group_panels)

        # Wrap in a single panel
        row_groups_panel = Panel(
            all_row_groups,
            title="[bold green]ROW GROUPS[/bold green]",
            border_style="green",
        )

        return Container(
            Static(row_groups_panel),
            classes="structure-section",
        )

    def _create_column_panel(self, col: ColumnStats) -> Panel:
        """Create a Rich Panel for a column chunk.

        Args:
            col: ColumnStats object

        Returns:
            Rich Panel with column chunk details
        """
        col_text = Text()

        # Type information
        type_str = col.physical_type
        if col.logical_type and col.logical_type != col.physical_type:
            type_str += f" ({col.logical_type})"
        col_text.append("Type: ", style="dim")
        col_text.append(f"{type_str}\n", style="cyan")

        # Compression
        col_text.append("Codec: ", style="dim")
        codec_style = "green" if col.compression != "UNCOMPRESSED" else "yellow"
        col_text.append(f"{col.compression}\n", style=codec_style)

        # Encoding
        if col.encodings:
            encodings_str = ", ".join(col.encodings)
            col_text.append("Encoding: ", style="dim")
            col_text.append(encodings_str, style="dim")

        return Panel(
            col_text,
            title=f"[bold cyan]{col.name}[/bold cyan]",
            border_style="dim",
            padding=(0, 1),
        )

    def _render_page_indexes(self, file_info: ParquetFileInfo) -> Static:
        """Render the page indexes section using Rich Panel.

        Args:
            file_info: ParquetFileInfo object

        Returns:
            Static widget with page index information
        """
        # Note: PyArrow doesn't expose page index data directly in Python API
        # We can only check if they exist, not read their contents

        content = Text()
        content.append("Status: ", style="bold")
        content.append("Not present", style="yellow")

        panel = Panel(
            content,
            title="[bold magenta]PAGE INDEXES[/bold magenta]",
            border_style="magenta",
        )

        return Static(panel)

    def _render_footer(self, file_info: ParquetFileInfo) -> Static:
        """Render the file footer section using Rich Panel.

        Args:
            file_info: ParquetFileInfo object

        Returns:
            Container with footer information
        """
        footer_text = Text()
        footer_text.append("Total Rows: ", style="bold")
        footer_text.append(f"{file_info.num_rows:,}\n")
        footer_text.append("Row Groups: ", style="bold")
        footer_text.append(f"{file_info.num_row_groups}\n")
        footer_text.append("Metadata Size: ", style="bold")
        footer_text.append("N/A\n", style="dim")
        footer_text.append("Footer Size: ", style="bold")
        footer_text.append("4 bytes\n")
        footer_text.append("Magic Number: ", style="bold")
        footer_text.append("PAR1", style="yellow")

        panel = Panel(
            footer_text,
            title="[bold blue]FOOTER[/bold blue]",
            border_style="blue",
        )

        return Static(panel)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string (e.g., "1.2 MB")
        """
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
