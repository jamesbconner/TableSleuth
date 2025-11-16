"""Row groups view widget for displaying Parquet row group information."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Collapsible, Static

from table_sleuth.models.parquet import ParquetFileInfo


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

            # Create details content
            details_lines = []
            details_lines.append(f"[bold]Row Count:[/bold] {rg.num_rows:,}")
            details_lines.append(f"[bold]Size:[/bold] {size_str}")
            details_lines.append("")
            details_lines.append(f"[bold]Columns ({len(rg.columns)}):[/bold]")

            # Show first 5 columns with stats
            for col in rg.columns[:5]:
                details_lines.append(f"  • {col.name}")
                details_lines.append(f"    Type: {col.physical_type}")
                if col.null_count is not None:
                    details_lines.append(f"    Nulls: {col.null_count:,}")
                if col.min_value is not None and col.max_value is not None:
                    # Truncate long values
                    min_str = str(col.min_value)[:30]
                    max_str = str(col.max_value)[:30]
                    details_lines.append(f"    Min: {min_str}")
                    details_lines.append(f"    Max: {max_str}")

            if len(rg.columns) > 5:
                details_lines.append(f"  ... and {len(rg.columns) - 5} more columns")

            # Create collapsible widget
            collapsible = Collapsible(
                Static("\n".join(details_lines), classes="rg-details"),
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
