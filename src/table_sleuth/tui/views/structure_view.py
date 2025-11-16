"""Structure view widget for displaying Parquet file physical structure."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static

from table_sleuth.models.parquet import ColumnStats, ParquetFileInfo

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
        margin: 1 0;
        padding: 1;
    }

    .header-section {
        border: heavy $accent;
    }

    .row-group-section {
        border: heavy $success;
    }

    .page-index-section {
        border: heavy $warning;
    }

    .footer-section {
        border: heavy $secondary;
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
            widgets: list[Container | Static] = []

            try:
                widgets.append(self._render_header(file_info))
            except Exception as e:
                logger.warning(f"Failed to render header: {e}")
                widgets.append(Static("[red]Error rendering header[/red]"))

            try:
                widgets.extend(self._render_row_groups(file_info))
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

    def _render_header(self, file_info: ParquetFileInfo) -> Container:
        """Render the file header section.

        Args:
            file_info: ParquetFileInfo object

        Returns:
            Container with header information
        """
        content = []
        content.append("[bold]HEADER[/bold]")
        content.append("")
        content.append("Magic Number: PAR1")
        content.append("Size: 4 bytes")

        return Container(
            Static("\n".join(content)),
            classes="structure-section header-section",
        )

    def _render_row_groups(self, file_info: ParquetFileInfo) -> list[Container]:
        """Render all row group sections.

        Args:
            file_info: ParquetFileInfo object

        Returns:
            List of Container widgets, one per row group
        """
        row_group_widgets = []

        for rg in file_info.row_groups:
            # Row group header
            header_text = (
                f"[bold]ROW GROUP {rg.index}[/bold]\n"
                f"Rows: {rg.num_rows:,} | "
                f"Size: {self._format_size(rg.total_byte_size)}"
            )

            # Build column chunks text
            column_chunks_text = []
            for col in rg.columns:
                col_text = self._format_column_chunk(col)
                column_chunks_text.append(col_text)
                column_chunks_text.append("")  # Spacing between columns

            # Combine header and column chunks
            full_text = header_text + "\n\n" + "\n".join(column_chunks_text)

            # Create row group container
            rg_container = Container(
                Static(full_text),
                classes="structure-section row-group-section",
            )

            row_group_widgets.append(rg_container)

        return row_group_widgets

    def _format_column_chunk(self, col: ColumnStats) -> str:
        """Format column chunk information.

        Args:
            col: ColumnStats object

        Returns:
            Formatted string with column chunk details
        """
        lines = []

        # Column name
        lines.append(f"[bold]{col.name}[/bold]")

        # Type information
        type_str = col.physical_type
        if col.logical_type and col.logical_type != col.physical_type:
            type_str += f" ({col.logical_type})"
        lines.append(f"Type: {type_str}")

        # Size (not directly available, show N/A)
        lines.append("Size: N/A")

        # Compression and encoding
        lines.append(f"Codec: {col.compression}")
        if col.encodings:
            encodings_str = ", ".join(col.encodings)
            lines.append(f"Encoding: {encodings_str}")

        return "\n".join(lines)

    def _render_page_indexes(self, file_info: ParquetFileInfo) -> Container:
        """Render the page indexes section.

        Args:
            file_info: ParquetFileInfo object

        Returns:
            Container with page index information
        """
        content = []
        content.append("[bold]PAGE INDEXES[/bold]")
        content.append("")

        # Note: PyArrow doesn't expose page index information directly
        # We'll show a placeholder message
        content.append("[dim]Page index information not available[/dim]")
        content.append("")
        content.append("Column Index: Per-page statistics for filtering")
        content.append("Offset Index: Page locations for random access")

        return Container(
            Static("\n".join(content)),
            classes="structure-section page-index-section",
        )

    def _render_footer(self, file_info: ParquetFileInfo) -> Container:
        """Render the file footer section.

        Args:
            file_info: ParquetFileInfo object

        Returns:
            Container with footer information
        """
        content = []
        content.append("[bold]FOOTER[/bold]")
        content.append("")
        content.append(f"Total Rows: {file_info.num_rows:,}")
        content.append(f"Row Groups: {file_info.num_row_groups}")

        # Calculate approximate metadata size
        # (actual metadata size not directly available from PyArrow)
        metadata_size = "N/A"
        content.append(f"Metadata Size: {metadata_size}")

        content.append("Footer Size: 4 bytes")
        content.append("Magic Number: PAR1")

        return Container(
            Static("\n".join(content)),
            classes="structure-section footer-section",
        )

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
