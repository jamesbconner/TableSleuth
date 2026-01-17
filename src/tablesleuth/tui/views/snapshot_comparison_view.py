"""Comparison and performance test views for Iceberg snapshots."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Button, DataTable, Input, Select, Static

from tablesleuth.models.iceberg import (
    PerformanceComparison,
    SnapshotComparison,
)


class SnapshotComparisonView(Container):
    """Widget for displaying snapshot comparison results."""

    DEFAULT_CSS = """
    SnapshotComparisonView {
        height: 100%;
        overflow-y: auto;
    }
    """

    def __init__(
        self,
        comparison: SnapshotComparison | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the comparison view.

        Args:
            comparison: Optional comparison to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._comparison = comparison

    def compose(self) -> ComposeResult:
        """Compose the comparison view."""
        yield Static("", id="comparison-content")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        if self._comparison:
            self.update_comparison(self._comparison)
        else:
            self.show_placeholder()

    def show_placeholder(self) -> None:
        """Show placeholder message."""
        content = self.query_one("#comparison-content", Static)
        content.update("[dim]Select exactly 2 snapshots in Compare Mode to view comparison[/dim]")

    def update_comparison(self, comparison: SnapshotComparison) -> None:
        """Update the displayed comparison.

        Args:
            comparison: SnapshotComparison object
        """
        self._comparison = comparison
        content = self.query_one("#comparison-content", Static)

        lines = []

        # Snapshot info
        lines.append("[bold cyan]Comparing Snapshots[/bold cyan]")
        lines.append(f"  Snapshot A: {comparison.snapshot_a.snapshot_id}")
        lines.append(f"  Snapshot B: {comparison.snapshot_b.snapshot_id}")
        lines.append("")

        # File changes
        lines.append("[bold cyan]File Changes[/bold cyan]")
        lines.append(f"  Data Files Added: {comparison.data_files_added:,}")
        lines.append(f"  Data Files Removed: {comparison.data_files_removed:,}")
        lines.append(f"  Delete Files Added: {comparison.delete_files_added:,}")
        lines.append(f"  Delete Files Removed: {comparison.delete_files_removed:,}")
        lines.append("")

        # Record changes
        lines.append("[bold cyan]Record Changes[/bold cyan]")
        lines.append(f"  Records Added: {comparison.records_added:,}")
        lines.append(f"  Records Deleted: {comparison.records_deleted:,}")
        lines.append(f"  Net Change: {comparison.records_delta:,}")
        lines.append("")

        # Size changes
        lines.append("[bold cyan]Size Changes[/bold cyan]")
        lines.append(f"  Size Added: {self._format_size(comparison.size_added_bytes)}")
        lines.append(f"  Size Removed: {self._format_size(comparison.size_removed_bytes)}")
        lines.append(f"  Net Change: {self._format_size(comparison.size_delta_bytes)}")
        lines.append("")

        # MOR metrics
        lines.append("[bold yellow]Merge-on-Read Metrics[/bold yellow]")
        lines.append(f"  Snapshot A Delete Ratio: {comparison.snapshot_a.delete_ratio:.2f}%")
        lines.append(f"  Snapshot B Delete Ratio: {comparison.snapshot_b.delete_ratio:.2f}%")
        lines.append(f"  Change: {comparison.delete_ratio_change:+.2f}%")
        lines.append("")
        lines.append(
            f"  Snapshot A Read Amplification: {comparison.snapshot_a.read_amplification:.2f}x"
        )
        lines.append(
            f"  Snapshot B Read Amplification: {comparison.snapshot_b.read_amplification:.2f}x"
        )
        lines.append(f"  Change: {comparison.read_amplification_change:+.2f}x")
        lines.append("")

        # Compaction recommendation
        if comparison.needs_compaction:
            lines.append(f"[yellow]{comparison.compaction_recommendation}[/yellow]")
        else:
            lines.append(f"[green]{comparison.compaction_recommendation}[/green]")

        content.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the comparison view."""
        self._comparison = None
        self.show_placeholder()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format size in human-readable format.

        Handles both positive and negative sizes correctly.
        """
        # Handle negative sizes
        is_negative = size_bytes < 0
        size = float(abs(size_bytes))

        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                result = f"{size:.1f} {unit}"
                return f"-{result}" if is_negative else result
            size /= 1024.0

        result = f"{size:.1f} PB"
        return f"-{result}" if is_negative else result


class PerformanceTestView(Container):
    """Widget for running and displaying performance tests."""

    DEFAULT_CSS = """
    PerformanceTestView {
        height: 100%;
        overflow-y: auto;
    }

    #test-controls {
        height: auto;
        padding: 1;
        background: $surface;
        border-bottom: solid $primary;
    }

    #test-results {
        height: 1fr;
        padding: 1;
    }

    #query-input {
        width: 100%;
        margin-bottom: 1;
    }

    #query-template-select {
        width: 50%;
        margin-bottom: 1;
    }

    #run-test-button {
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
        """Initialize the performance test view.

        Args:
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._table_a_name: str | None = None
        self._table_b_name: str | None = None
        self._test_result: PerformanceComparison | None = None

    def compose(self) -> ComposeResult:
        """Compose the performance test view."""
        with Vertical(id="test-controls"):
            yield Static("", id="table-names-info")
            yield Select(
                options=[
                    ("Full Scan", "full_scan"),
                    ("Sample Rows", "sample_rows"),
                    ("Table Stats", "table_stats"),
                    ("Filtered Scan", "filtered_scan"),
                    ("Aggregation", "aggregation"),
                    ("Point Lookup", "point_lookup"),
                    ("Column Stats", "column_stats"),
                    ("Distinct Count", "distinct_count"),
                ],
                prompt="Select query template",
                id="query-template-select",
            )
            yield Input(
                placeholder="Enter SQL query (use {table} placeholder)",
                id="query-input",
            )
            yield Button("Run Performance Test", id="run-test-button", variant="primary")

        with Vertical(id="test-results"):
            yield Static("", id="results-content")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        self.show_placeholder()

    def show_placeholder(self) -> None:
        """Show placeholder message."""
        results = self.query_one("#results-content", Static)
        results.update("[dim]Configure and run a performance test to see results[/dim]")

    def set_table_names(self, table_a: str, table_b: str) -> None:
        """Set the registered table names for testing.

        Args:
            table_a: Name of first snapshot table
            table_b: Name of second snapshot table
        """
        self._table_a_name = table_a
        self._table_b_name = table_b

        # Update info display
        info = self.query_one("#table-names-info", Static)
        info.update(
            f"[bold]Registered Tables:[/bold]\n  Snapshot A: {table_a}\n  Snapshot B: {table_b}"
        )

    def update_results(self, comparison: PerformanceComparison) -> None:
        """Update the displayed test results.

        Args:
            comparison: PerformanceComparison object
        """
        self._test_result = comparison
        results = self.query_one("#results-content", Static)

        lines = []

        # Query
        lines.append("[bold cyan]Query[/bold cyan]")
        lines.append(f"  {comparison.query}")
        lines.append("")

        # Execution time
        lines.append("[bold cyan]Execution Time[/bold cyan]")
        lines.append(
            f"  {comparison.table_a_name}: {comparison.metrics_a.execution_time_ms:.2f} ms"
        )
        lines.append(
            f"  {comparison.table_b_name}: {comparison.metrics_b.execution_time_ms:.2f} ms"
        )
        delta_pct = comparison.execution_time_delta_pct
        delta_color = "red" if delta_pct > 10 else "green" if delta_pct < -10 else "yellow"
        lines.append(f"  [{delta_color}]Delta: {delta_pct:+.1f}%[/{delta_color}]")
        lines.append("")

        # Files scanned
        lines.append("[bold cyan]Files Scanned[/bold cyan]")
        lines.append(f"  {comparison.table_a_name}: {comparison.metrics_a.files_scanned:,}")
        lines.append(f"  {comparison.table_b_name}: {comparison.metrics_b.files_scanned:,}")
        files_delta_pct = comparison.files_scanned_delta_pct
        files_color = "red" if files_delta_pct > 0 else "green"
        lines.append(f"  [{files_color}]Delta: {files_delta_pct:+.1f}%[/{files_color}]")
        lines.append("")

        # Scan efficiency
        lines.append("[bold cyan]Scan Efficiency[/bold cyan]")
        lines.append(f"  {comparison.table_a_name}: {comparison.metrics_a.scan_efficiency:.1f}%")
        lines.append(f"  {comparison.table_b_name}: {comparison.metrics_b.scan_efficiency:.1f}%")
        lines.append("")

        # Analysis
        lines.append("[bold yellow]Analysis[/bold yellow]")
        for line in comparison.analysis.split("\n"):
            lines.append(f"  {line}")

        results.update("\n".join(lines))

    def clear(self) -> None:
        """Clear the test results."""
        self._test_result = None
        self._table_a_name = None
        self._table_b_name = None
        self.show_placeholder()
