"""File detail view widget for displaying Parquet file metadata."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Static

from tablesleuth.models.parquet import ParquetFileInfo


class FileDetailView(Container):
    """Widget for displaying detailed metadata for a Parquet file.

    Displays:
    - File path
    - File size and row count
    - Number of row groups and columns
    - Format version and compression
    - Creator information
    """

    DEFAULT_CSS = """
    FileDetailView {
        height: 100%;
        border: solid $primary;
    }

    FileDetailView > Static#detail-header {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    FileDetailView > Vertical {
        height: 1fr;
        padding: 1;
    }

    FileDetailView .detail-label {
        color: $text-muted;
        text-style: bold;
    }

    FileDetailView .detail-value {
        color: $text;
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
        """Initialize the file detail view.

        Args:
            file_info: Optional ParquetFileInfo to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._file_info = file_info

    def compose(self) -> ComposeResult:
        """Compose the file detail view."""
        yield Static("File Details", id="detail-header")
        yield Vertical(
            Static("No file selected", id="detail-content"),
            id="detail-container",
        )

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        if self._file_info:
            self.update_file_info(self._file_info)

    def update_file_info(self, file_info: ParquetFileInfo) -> None:
        """Update the displayed file information.

        Args:
            file_info: ParquetFileInfo object with file metadata
        """
        self._file_info = file_info

        # Build the detail content
        content_lines = []

        # File path
        content_lines.append(f"[bold]Path:[/bold] {file_info.path}")
        content_lines.append("")

        # Check if this is an Iceberg file
        # Note: Full Iceberg context requires metadata location tracking
        # which would need to be added to FileRef.extra during discovery
        if hasattr(file_info, "source") and file_info.source == "iceberg":
            content_lines.append("[bold cyan]Iceberg File[/bold cyan]")
            content_lines.append("  This file is part of an Iceberg table")
            content_lines.append(
                "  [dim]Use 'tablesleuth iceberg <metadata>' to view snapshots[/dim]"
            )
            content_lines.append("")

        # File statistics
        content_lines.append("[bold]File Statistics:[/bold]")
        content_lines.append(f"  Size: {self._format_size(file_info.file_size_bytes)}")
        content_lines.append(f"  Rows: {file_info.num_rows:,}")
        content_lines.append(f"  Row Groups: {file_info.num_row_groups}")
        content_lines.append(f"  Columns: {file_info.num_columns}")
        content_lines.append("")

        # Format information
        content_lines.append("[bold]Format Information:[/bold]")
        content_lines.append(f"  Version: {file_info.format_version}")

        # Get compression from first column if available
        if file_info.columns:
            compression = file_info.columns[0].compression
            content_lines.append(f"  Compression: {compression}")

        if file_info.created_by:
            content_lines.append(f"  Created by: {file_info.created_by}")

        content_lines.append("")

        # Row group details
        if file_info.row_groups:
            content_lines.append("[bold]Row Groups:[/bold]")
            for rg in file_info.row_groups:
                size_str = self._format_size(rg.total_byte_size)
                content_lines.append(f"  Group {rg.index}: {rg.num_rows:,} rows, {size_str}")

        # Update the content
        content = self.query_one("#detail-content", Static)
        content.update("\n".join(content_lines))

    def clear(self) -> None:
        """Clear the file detail view."""
        self._file_info = None
        content = self.query_one("#detail-content", Static)
        content.update("No file selected")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format file size in human-readable format.

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
