"""Detail view widgets for Iceberg snapshots."""

from __future__ import annotations

from datetime import datetime

from rich.table import Table as RichTable
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import DataTable, Static

from tablesleuth.models.iceberg import (
    IcebergSnapshotDetails,
    IcebergSnapshotInfo,
    PartitionSpecInfo,
    SchemaInfo,
    SortOrderInfo,
)


class SnapshotOverviewView(Container):
    """Widget for displaying snapshot overview information."""

    DEFAULT_CSS = """
    SnapshotOverviewView {
        height: 100%;
        overflow-y: auto;
    }
    """

    def __init__(
        self,
        snapshot: IcebergSnapshotInfo | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the overview view.

        Args:
            snapshot: Optional snapshot to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        """Compose the overview view."""
        yield Static("", id="overview-content")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        if self._snapshot:
            self.update_snapshot(self._snapshot)

    def update_snapshot(self, snapshot: IcebergSnapshotInfo) -> None:
        """Update the displayed snapshot.

        Args:
            snapshot: IcebergSnapshotInfo object
        """
        self._snapshot = snapshot
        content = self.query_one("#overview-content", Static)

        # Format timestamp
        timestamp = datetime.fromtimestamp(snapshot.timestamp_ms / 1000)
        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Build overview content
        lines = []

        # Basic info
        lines.append("[bold cyan]Snapshot Information[/bold cyan]")
        lines.append(f"  Snapshot ID: {snapshot.snapshot_id}")
        lines.append(f"  Parent ID: {snapshot.parent_snapshot_id or 'None'}")
        lines.append(f"  Timestamp: {timestamp_str}")
        lines.append(f"  Operation: {snapshot.operation}")
        lines.append(f"  Schema ID: {snapshot.schema_id}")
        lines.append("")

        # File statistics
        lines.append("[bold cyan]File Statistics[/bold cyan]")
        lines.append(f"  Data Files: {snapshot.total_data_files:,}")
        lines.append(f"  Delete Files: {snapshot.total_delete_files:,}")
        lines.append(f"  Total Size: {self._format_size(snapshot.total_size_bytes)}")
        lines.append("")

        # Record statistics
        lines.append("[bold cyan]Record Statistics[/bold cyan]")
        lines.append(f"  Total Records: {snapshot.total_records:,}")
        lines.append(f"  Position Deletes: {snapshot.position_deletes:,}")
        lines.append(f"  Equality Deletes: {snapshot.equality_deletes:,}")
        lines.append("")

        # MOR metrics (if deletes present)
        if snapshot.has_deletes:
            lines.append("[bold yellow]Merge-on-Read Metrics[/bold yellow]")
            lines.append(f"  Delete Ratio: {snapshot.delete_ratio:.2f}%")
            lines.append(f"  Read Amplification: {snapshot.read_amplification:.2f}x")

            # Impact assessment
            if snapshot.delete_ratio > 15:
                lines.append("  [red]⚠️  High MOR overhead - compaction recommended[/red]")
            elif snapshot.delete_ratio > 5:
                lines.append("  [yellow]⚠️  Medium MOR overhead - consider compaction[/yellow]")
            else:
                lines.append("  [green]✓ Low MOR overhead[/green]")
            lines.append("")

        # Manifest list
        lines.append("[bold cyan]Metadata[/bold cyan]")
        lines.append(f"  Manifest List: {snapshot.manifest_list}")

        content.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the overview view."""
        self._snapshot = None
        content = self.query_one("#overview-content", Static)
        content.update("Select a snapshot to view details")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in human-readable format."""
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


class SnapshotFilesView(Container):
    """Widget for displaying snapshot files."""

    DEFAULT_CSS = """
    SnapshotFilesView {
        height: 100%;
        overflow-y: auto;
    }

    SnapshotFilesView > DataTable {
        height: 100%;
    }
    """

    def __init__(
        self,
        details: IcebergSnapshotDetails | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the files view.

        Args:
            details: Optional snapshot details to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._details = details

    def compose(self) -> ComposeResult:
        """Compose the files view."""
        yield DataTable(id="files-table", cursor_type="row")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        table = self.query_one("#files-table", DataTable)

        # Add columns
        table.add_columns("Type", "Path", "Size", "Records")

        if self._details:
            self.update_details(self._details)

    def update_details(self, details: IcebergSnapshotDetails) -> None:
        """Update the displayed files.

        Args:
            details: IcebergSnapshotDetails object
        """
        # Only update if details changed
        if self._details is details:
            return

        self._details = details
        table = self.query_one("#files-table", DataTable)

        # Clear existing rows (preserve columns)
        table.clear(columns=False)

        # Add data files
        for file_info in details.data_files:
            table.add_row(
                "Data",
                str(file_info.get("file_path", "N/A")),
                self._format_size(file_info.get("file_size_bytes", 0)),
                f"{file_info.get('record_count', 0):,}",
            )

        # Add delete files
        for file_info in details.delete_files:
            table.add_row(
                "[yellow]Delete[/yellow]",
                str(file_info.get("file_path", "N/A")),
                self._format_size(file_info.get("file_size_bytes", 0)),
                f"{file_info.get('record_count', 0):,}",
            )

    def clear(self) -> None:
        """Clear the files view."""
        self._details = None
        table = self.query_one("#files-table", DataTable)
        table.clear()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in human-readable format."""
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


class SnapshotSchemaView(Container):
    """Widget for displaying snapshot schema."""

    DEFAULT_CSS = """
    SnapshotSchemaView {
        height: 100%;
        overflow-y: auto;
    }

    SnapshotSchemaView > DataTable {
        height: 100%;
    }
    """

    def __init__(
        self,
        schema: SchemaInfo | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the schema view.

        Args:
            schema: Optional schema to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._schema = schema

    def compose(self) -> ComposeResult:
        """Compose the schema view."""
        yield DataTable(id="schema-table", cursor_type="row")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        table = self.query_one("#schema-table", DataTable)

        # Add columns
        table.add_columns("Field ID", "Name", "Type", "Required", "Doc")

        if self._schema:
            self.update_schema(self._schema)

    def update_schema(self, schema: SchemaInfo) -> None:
        """Update the displayed schema.

        Args:
            schema: SchemaInfo object
        """
        # Only update if schema changed
        if self._schema is schema:
            return

        self._schema = schema
        table = self.query_one("#schema-table", DataTable)

        # Clear existing rows (preserve columns)
        table.clear(columns=False)

        # Add schema fields
        for field in schema.fields:
            required_str = "✓" if field.required else ""
            doc_str = field.doc or ""

            table.add_row(
                str(field.field_id),
                field.name,
                field.field_type,
                required_str,
                doc_str,
            )

    def clear(self) -> None:
        """Clear the schema view."""
        self._schema = None
        table = self.query_one("#schema-table", DataTable)
        table.clear()


class SnapshotDeletesView(Container):
    """Widget for displaying delete file details."""

    DEFAULT_CSS = """
    SnapshotDeletesView {
        height: 100%;
        overflow-y: auto;
    }
    """

    def __init__(
        self,
        details: IcebergSnapshotDetails | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the deletes view.

        Args:
            details: Optional snapshot details to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._details = details

    def compose(self) -> ComposeResult:
        """Compose the deletes view."""
        yield Static("", id="deletes-content")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        if self._details:
            self.update_details(self._details)

    def update_details(self, details: IcebergSnapshotDetails) -> None:
        """Update the displayed delete information.

        Args:
            details: IcebergSnapshotDetails object
        """
        self._details = details
        content = self.query_one("#deletes-content", Static)

        if not details.delete_files:
            content.update("[dim]No delete files in this snapshot[/dim]")
            return

        lines = []

        # Summary
        lines.append("[bold yellow]Delete Files Summary[/bold yellow]")
        lines.append(f"  Total Delete Files: {len(details.delete_files)}")

        total_delete_records = sum(f.get("record_count", 0) for f in details.delete_files)
        lines.append(f"  Total Delete Records: {total_delete_records:,}")

        total_delete_size = sum(f.get("file_size_bytes", 0) for f in details.delete_files)
        lines.append(f"  Total Delete Size: {self._format_size(total_delete_size)}")
        lines.append("")

        # MOR impact
        snapshot = details.snapshot_info
        lines.append("[bold yellow]Merge-on-Read Impact[/bold yellow]")
        lines.append(f"  Delete Ratio: {snapshot.delete_ratio:.2f}%")
        lines.append(f"  Read Amplification: {snapshot.read_amplification:.2f}x")
        lines.append("")

        # Recommendation
        if snapshot.delete_ratio > 15:
            lines.append("[red]⚠️  High delete ratio detected[/red]")
            lines.append("[red]   Compaction is strongly recommended[/red]")
        elif snapshot.delete_ratio > 5:
            lines.append("[yellow]⚠️  Medium delete ratio detected[/yellow]")
            lines.append("[yellow]   Consider running compaction[/yellow]")
        else:
            lines.append("[green]✓ Delete ratio is acceptable[/green]")

        content.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the deletes view."""
        self._details = None
        content = self.query_one("#deletes-content", Static)
        content.update("Select a snapshot to view delete files")

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in human-readable format."""
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


class SnapshotPropertiesView(Container):
    """Widget for displaying snapshot properties."""

    DEFAULT_CSS = """
    SnapshotPropertiesView {
        height: 100%;
        overflow-y: auto;
    }

    SnapshotPropertiesView > DataTable {
        height: 100%;
    }
    """

    def __init__(
        self,
        snapshot: IcebergSnapshotInfo | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the properties view.

        Args:
            snapshot: Optional snapshot to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        """Compose the properties view."""
        yield DataTable(id="properties-table", cursor_type="row")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        table = self.query_one("#properties-table", DataTable)

        # Add columns
        table.add_columns("Property", "Value")

        if self._snapshot:
            self.update_snapshot(self._snapshot)

    def update_snapshot(self, snapshot: IcebergSnapshotInfo) -> None:
        """Update the displayed properties.

        Args:
            snapshot: IcebergSnapshotInfo object
        """
        # Only update if snapshot changed
        if self._snapshot is snapshot:
            return

        self._snapshot = snapshot
        table = self.query_one("#properties-table", DataTable)

        # Clear existing rows (preserve columns)
        table.clear(columns=False)

        # Add summary properties
        for key, value in snapshot.summary.items():
            table.add_row(key, str(value))

    def clear(self) -> None:
        """Clear the properties view."""
        self._snapshot = None
        table = self.query_one("#properties-table", DataTable)
        table.clear()
