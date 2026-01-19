"""File list view widget for displaying Parquet files."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Static

from tablesleuth.models.file_ref import FileRef


class FileListView(Container):
    """Widget for displaying a list of Parquet files.

    Displays files in a DataTable with columns for:
    - Path (filename only)
    - Size (formatted)
    - Rows (record count)
    - Row Groups

    Supports keyboard navigation and file selection events.
    """

    DEFAULT_CSS = """
    FileListView {
        height: 100%;
        border: solid $primary;
    }

    FileListView > Static {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    FileListView > DataTable {
        height: 1fr;
    }
    """

    def __init__(
        self,
        files: list[FileRef] | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the file list view.

        Args:
            files: Optional initial list of files to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._files = files or []
        self._table: DataTable | None = None

    def compose(self) -> ComposeResult:
        """Compose the file list view."""
        yield Static("Files", id="file-list-header")
        yield DataTable(id="file-list-table", cursor_type="row")

    def on_mount(self) -> None:
        """Set up the data table when mounted."""
        self._table = self.query_one("#file-list-table", DataTable)

        # Add columns
        self._table.add_columns("Path", "Size", "Rows")

        # Populate with initial files
        if self._files:
            self.update_files(self._files)

    def update_files(self, files: list[FileRef]) -> None:
        """Update the file list.

        Args:
            files: List of FileRef objects to display
        """
        self._files = files

        if self._table is None:
            return

        # Clear existing rows
        self._table.clear()

        # Add rows for each file
        for file_ref in files:
            # For display, show relative path from common prefix or full path
            # This preserves partition information while keeping display manageable
            display_path = file_ref.path

            # For S3 paths, show path relative to bucket (handle both s3:// and s3a://)
            if display_path.startswith("s3a://"):
                # Remove s3a:// prefix and show from bucket onwards
                display_path = display_path[6:]  # Remove "s3a://"
            elif display_path.startswith("s3://"):
                # Remove s3:// prefix and show from bucket onwards
                display_path = display_path[5:]  # Remove "s3://"

            # For very long paths, show the last few segments to include partitions
            # but not the full absolute path
            path_parts = display_path.split("/")
            if len(path_parts) > 4:
                # Show last 4 segments (typically: table/partition1/partition2/file.parquet)
                display_path = "/".join(path_parts[-4:])

            # Format file size
            size_str = self._format_size(file_ref.file_size_bytes)

            # Format record count
            rows_str = f"{file_ref.record_count:,}" if file_ref.record_count is not None else "?"

            self._table.add_row(display_path, size_str, rows_str)

    def get_selected_file(self) -> FileRef | None:
        """Get the currently selected file.

        Returns:
            Selected FileRef or None if no selection
        """
        if self._table is None or not self._files:
            return None

        cursor_row = self._table.cursor_row
        if cursor_row < 0 or cursor_row >= len(self._files):
            return None

        return self._files[cursor_row]

    def show_aggregate_stats(self) -> None:
        """Show aggregate statistics for all files in the header."""
        if not self._files:
            return

        total_files = len(self._files)
        total_size = sum(f.file_size_bytes for f in self._files)
        total_rows = sum(f.record_count for f in self._files if f.record_count is not None)

        header = self.query_one("#file-list-header", Static)
        header.update(
            f"Files: {total_files} | Size: {self._format_size(total_size)} | Rows: {total_rows:,}"
        )

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
