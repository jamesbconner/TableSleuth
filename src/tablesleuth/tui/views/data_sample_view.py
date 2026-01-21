"""Data sample view widget for displaying Parquet file data samples."""

from __future__ import annotations

import logging
from typing import Any

import pyarrow as pa
import pyarrow.types
from pyarrow.parquet import ParquetFile
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input, Select, Static

from tablesleuth.models.parquet import ParquetFileInfo
from tablesleuth.utils.path_utils import is_s3_path

logger = logging.getLogger(__name__)


class DataSampleView(Container):
    """Widget for displaying sample data from Parquet files.

    Features:
    - Selectable columns with clickable buttons
    - Configurable row count (10, 50, 100, 500)
    - Efficient data loading with PyArrow (column pruning, row limiting)
    - Rich formatting for different data types
    - Horizontal split layout (column selector + data table)
    """

    DEFAULT_CSS = """
    DataSampleView {
        height: 100%;
        border: solid $primary;
    }

    DataSampleView > Static#sample-header {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    DataSampleView #sample-content {
        height: 1fr;
    }

    DataSampleView #sample-column-selector {
        width: 20%;
        height: 100%;
        border-right: solid $accent;
        padding: 1;
    }

    DataSampleView #sample-table-container {
        width: 80%;
    }

    DataSampleView #sample-table {
        height: 1fr;
    }

    DataSampleView #sample-status {
        padding: 0 1;
        color: $text-muted;
        text-align: right;
    }

    DataSampleView .selector-label {
        margin-top: 1;
        margin-bottom: 0;
        text-style: bold;
    }

    DataSampleView #select-buttons {
        height: auto;
        width: 100%;
    }

    DataSampleView #select-buttons Button {
        width: 1fr;
        min-width: 8;
        margin: 0 0 1 0;
    }

    DataSampleView #select-all-btn {
        margin-right: 1;
    }

    DataSampleView Select {
        width: 100%;
        margin-bottom: 1;
    }

    DataSampleView Input {
        width: 100%;
        margin-bottom: 1;
    }

    DataSampleView #column-list-scroll {
        height: 1fr;
        max-height: 100%;
        overflow-y: scroll;
        scrollbar-gutter: stable;
    }

    DataSampleView #column-list {
        height: auto;
        width: 100%;
    }

    DataSampleView .column-item {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    DataSampleView .column-item.selected {
        color: $success;
    }

    DataSampleView .column-item:hover {
        background: $accent;
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
        """Initialize the data sample view.

        Args:
            file_info: Optional ParquetFileInfo to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._file_info = file_info
        self._selected_columns: set[str] = set()
        self._row_count = 10
        self._data_table: DataTable | None = None
        self._parquet_file: ParquetFile | None = None
        self._column_filter = ""  # Filter text for columns

    def compose(self) -> ComposeResult:
        """Compose the data sample view."""
        yield Static("Data Sample (10 rows)", id="sample-header")

        with Horizontal(id="sample-content"):
            # Left side: Column selector (20%)
            with Vertical(id="sample-column-selector"):
                yield Static("Row Count:", classes="selector-label")
                yield Select(
                    options=[
                        ("10 rows", 10),
                        ("50 rows", 50),
                        ("100 rows", 100),
                        ("500 rows", 500),
                    ],
                    value=10,
                    id="row-count-select",
                )
                yield Static("Select:", classes="selector-label")
                with Horizontal(id="select-buttons"):
                    yield Button("All", id="select-all-btn", variant="primary")
                    yield Button("None", id="deselect-all-btn")
                yield Static("Filter Columns:", classes="selector-label")
                yield Input(placeholder="Type to filter...", id="column-filter")
                yield Static("Columns:", classes="selector-label")
                with VerticalScroll(id="column-list-scroll"):
                    yield Vertical(id="column-list")

            # Right side: Data table (80%)
            with Vertical(id="sample-table-container"):
                yield DataTable(id="sample-table", cursor_type="cell")
                yield Static("No file loaded", id="sample-status")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        self._data_table = self.query_one("#sample-table", DataTable)

        # Populate with initial data if available
        if self._file_info:
            self.update_file_info(self._file_info)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle row count selection changes.

        Args:
            event: Select changed event
        """
        if event.select.id == "row-count-select":
            self._row_count = int(event.value) if isinstance(event.value, int | str) else 10

            # Update header
            header = self.query_one("#sample-header", Static)
            header.update(f"Data Sample ({self._row_count} rows)")

            # Reload data with new row count
            self._load_sample_data()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes.

        Args:
            event: Input changed event
        """
        if event.input.id == "column-filter":
            self._column_filter = event.value.lower()
            self._update_column_list()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button pressed event
        """
        if event.button.id == "select-all-btn":
            self._select_all_columns()
        elif event.button.id == "deselect-all-btn":
            self._deselect_all_columns()

    def on_click(self, event: Any) -> None:
        """Handle clicks on column items.

        Args:
            event: Click event
        """
        # Check if click was on a column item
        if hasattr(event, "widget") and event.widget.has_class("column-item"):
            # Extract column name from the label (remove checkmark if present)
            # Static widgets store content in render() or as plain text
            try:
                # Try to get the rendered content
                rendered = event.widget.render()
                label = str(rendered.plain) if hasattr(rendered, "plain") else str(rendered)
            except Exception:
                # Fallback: try to get from render_str
                try:
                    label = event.widget.render_str()
                except Exception:
                    # Last resort: assume the widget was just updated with the text
                    logger.warning("Could not extract label from widget, skipping click")
                    return

            col_name = label[2:] if label.startswith("✓ ") else label.strip()

            if col_name in self._selected_columns:
                # Deselect column
                self._selected_columns.discard(col_name)
                event.widget.update(f"  {col_name}")
                event.widget.remove_class("selected")
            else:
                # Select column
                self._selected_columns.add(col_name)
                event.widget.update(f"✓ {col_name}")
                event.widget.add_class("selected")

            # Reload data with new column selection
            self._load_sample_data()

    def update_file_info(self, file_info: ParquetFileInfo, region: str | None = None) -> None:
        """Update the displayed file information and load sample data.

        Args:
            file_info: ParquetFileInfo with file metadata
            region: AWS region for S3 access (optional)
        """
        self._file_info = file_info

        # Load PyArrow ParquetFile for data reading (with S3 support)
        try:
            from tablesleuth.services.filesystem import FileSystem

            fs = FileSystem(region=region)
            if is_s3_path(file_info.path):
                filesystem = fs.get_filesystem(file_info.path)
                normalized_path = fs.normalize_s3_path(file_info.path)
                self._parquet_file = ParquetFile(normalized_path, filesystem=filesystem)
            else:
                self._parquet_file = ParquetFile(file_info.path)
        except Exception as e:
            logger.error(f"Could not load ParquetFile: {e}", exc_info=True)
            self._show_error(f"Error loading file: {e}")
            return

        # Initialize selected columns with all columns
        self._selected_columns = {col.name for col in file_info.columns}

        # Create column list
        self._create_column_list()

        # Load initial sample data
        self._load_sample_data()

    def clear(self) -> None:
        """Clear the data sample view."""
        self._file_info = None
        self._parquet_file = None
        self._selected_columns.clear()

        if self._data_table:
            self._data_table.clear(columns=True)

        # Reset header
        header = self.query_one("#sample-header", Static)
        header.update("Data Sample (10 rows)")

        # Clear column list
        container = self.query_one("#column-list", Vertical)
        container.remove_children()

        # Show "No file loaded" message
        self._update_status("No file loaded")

    def _create_column_list(self) -> None:
        """Create clickable list for column selection."""
        if self._file_info is None:
            logger.debug("No file_info available for creating column list")
            return

        try:
            container = self.query_one("#column-list", Vertical)
            container.remove_children()

            logger.debug(f"Creating column items for {len(self._file_info.columns)} columns")

            # Create Static widget for each column (NO ID - avoids conflicts)
            for col in self._file_info.columns:
                item = Static(
                    f"✓ {col.name}",  # Show checkmark for selected
                    classes="column-item selected",
                )
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

            # Create Static widget for each filtered column (NO ID - avoids conflicts)
            for col in filtered_columns:
                is_selected = col.name in self._selected_columns
                label = f"✓ {col.name}" if is_selected else f"  {col.name}"
                classes = "column-item selected" if is_selected else "column-item"

                item = Static(
                    label,
                    classes=classes,
                )
                container.mount(item)
        except Exception as e:
            logger.error(f"Error updating column list: {e}")

    def _load_sample_data(self) -> None:
        """Load sample data from Parquet file using PyArrow."""
        if self._file_info is None or self._parquet_file is None:
            return

        # Check if any columns are selected
        if not self._selected_columns:
            self._show_message("No columns selected. Please select at least one column.")
            return

        try:
            # Show loading indicator
            self._show_loading()

            # Determine which columns to read
            columns_to_read = list(self._selected_columns)

            # Read data with PyArrow (column pruning)
            table = self._parquet_file.read(
                columns=columns_to_read,
                use_threads=True,
            )

            # Limit to requested row count
            if len(table) > self._row_count:
                table = table.slice(0, self._row_count)

            # Update DataTable
            self._populate_data_table(table)

            # Update status
            total_rows = self._file_info.num_rows
            actual_rows = len(table)
            self._update_status(f"Showing {actual_rows:,} of {total_rows:,} rows")

        except Exception as e:
            logger.error(f"Failed to load sample data: {e}")
            self._show_error(f"Error loading data: {e}")

    def _populate_data_table(self, table: pa.Table) -> None:
        """Populate the DataTable with data from PyArrow table.

        Args:
            table: PyArrow table with sample data
        """
        if self._data_table is None:
            return

        # Clear existing data
        self._data_table.clear(columns=True)

        # Add columns
        for col_name in table.column_names:
            self._data_table.add_column(col_name, key=col_name)

        # Add rows with Rich formatting
        for i in range(len(table)):
            row_data = []
            for col_name in table.column_names:
                value = table[col_name][i].as_py()
                formatted_value = self._format_cell_value(value, table[col_name].type)
                row_data.append(formatted_value)

            self._data_table.add_row(*row_data)

    def _format_cell_value(self, value: Any, data_type: pa.DataType) -> Text:
        """Format a cell value with Rich styling.

        Args:
            value: The value to format
            data_type: PyArrow data type

        Returns:
            Rich Text object with appropriate styling
        """
        # Handle NULL values
        if value is None:
            return Text("NULL", style="dim red")

        # Handle different data types
        if pa.types.is_integer(data_type) or pa.types.is_floating(data_type):
            # Numeric values - cyan
            if isinstance(value, float):
                return Text(f"{value:.4f}", style="cyan")
            return Text(str(value), style="cyan")

        elif pa.types.is_string(data_type) or pa.types.is_large_string(data_type):
            # String values - green, truncate if too long
            str_value = str(value)
            if len(str_value) > 50:
                str_value = str_value[:47] + "..."
            return Text(str_value, style="green")

        elif pa.types.is_date(data_type) or pa.types.is_timestamp(data_type):
            # Date/timestamp values - yellow
            return Text(str(value), style="yellow")

        elif pa.types.is_boolean(data_type):
            # Boolean values - magenta
            return Text(str(value), style="magenta")

        elif pa.types.is_decimal(data_type):
            # Decimal values - cyan
            return Text(str(value), style="cyan")

        elif pa.types.is_list(data_type) or pa.types.is_struct(data_type):
            # Complex types - show summary
            summary = self._format_complex_type(value)
            return Text(summary, style="dim")

        else:
            # Default - no special styling
            str_value = str(value)
            if len(str_value) > 50:
                str_value = str_value[:47] + "..."
            return Text(str_value)

    @staticmethod
    def _format_complex_type(value: Any) -> str:
        """Format complex types (lists, structs) as summary.

        Args:
            value: Complex value

        Returns:
            Summary string
        """
        if isinstance(value, list):
            return f"[{len(value)} items]"
        elif isinstance(value, dict):
            return f"{{{len(value)} fields}}"
        else:
            return str(value)[:50]

    def _select_all_columns(self) -> None:
        """Select all columns."""
        if self._file_info is None:
            return

        # Update column items
        for item in self.query(".column-item"):
            # Extract column name from current label
            try:
                if hasattr(item, "update"):
                    rendered = item.render()
                    label = str(rendered.plain) if hasattr(rendered, "plain") else str(rendered)
                    col_name = label[2:] if label.startswith("✓ ") else label.strip()

                    # Update to show selected
                    item.update(f"✓ {col_name}")
                    item.add_class("selected")
            except Exception as e:
                logger.warning(f"Could not update column item: {e}")

        # Update selected columns set
        self._selected_columns = {col.name for col in self._file_info.columns}

        # Reload data
        self._load_sample_data()

    def _deselect_all_columns(self) -> None:
        """Deselect all columns."""
        # Update column items
        for item in self.query(".column-item"):
            # Extract column name from current label
            try:
                if hasattr(item, "update"):
                    rendered = item.render()
                    label = str(rendered.plain) if hasattr(rendered, "plain") else str(rendered)
                    col_name = label[2:] if label.startswith("✓ ") else label.strip()

                    # Update to show deselected
                    item.update(f"  {col_name}")
                    item.remove_class("selected")
            except Exception as e:
                logger.warning(f"Could not update column item: {e}")

        # Clear selected columns
        self._selected_columns.clear()

        # Clear table and show message
        if self._data_table:
            self._data_table.clear(columns=True)

        self._show_message("No columns selected. Please select at least one column.")

    def _show_loading(self) -> None:
        """Display loading indicator in status area."""
        self._update_status("Loading data...")

    def _show_error(self, message: str) -> None:
        """Display error message.

        Args:
            message: Error message to display
        """
        self._update_status(f"Error: {message}")

        # Also clear the table
        if self._data_table:
            self._data_table.clear(columns=True)

    def _show_message(self, message: str) -> None:
        """Display informational message.

        Args:
            message: Message to display
        """
        self._update_status(message)

    def _update_status(self, message: str) -> None:
        """Update status Static widget with message.

        Args:
            message: Status message
        """
        status = self.query_one("#sample-status", Static)
        status.update(message)
