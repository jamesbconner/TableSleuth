"""Schema view widget for displaying Parquet file schema."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Input, Static

from table_sleuth.models.parquet import ParquetFileInfo


class SchemaView(Container):
    """Widget for displaying Parquet file schema.

    Displays columns in a DataTable with:
    - Column name
    - Physical type
    - Logical type

    Supports column filtering by name or type.
    """

    DEFAULT_CSS = """
    SchemaView {
        height: 100%;
        border: solid $primary;
    }

    SchemaView > Static#schema-header {
        background: $primary;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    SchemaView > Input {
        margin: 0 1;
        border: solid $accent;
    }

    SchemaView > DataTable {
        height: 1fr;
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
        """Initialize the schema view.

        Args:
            file_info: Optional ParquetFileInfo to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._file_info = file_info
        self._table: DataTable | None = None
        self._filter_input: Input | None = None

    def compose(self) -> ComposeResult:
        """Compose the schema view."""
        yield Static("Schema", id="schema-header")
        yield Input(placeholder="Filter columns...", id="schema-filter")
        yield DataTable(id="schema-table", cursor_type="row")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        self._table = self.query_one("#schema-table", DataTable)
        self._filter_input = self.query_one("#schema-filter", Input)

        # Add columns
        self._table.add_columns("Column", "Physical Type", "Logical Type")

        # Populate with initial data
        if self._file_info:
            self.update_schema(self._file_info)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes.

        Args:
            event: Input changed event
        """
        if event.input.id == "schema-filter":
            self._apply_filter(event.value)

    def update_schema(self, file_info: ParquetFileInfo) -> None:
        """Update the displayed schema.

        Args:
            file_info: ParquetFileInfo with schema information
        """
        self._file_info = file_info

        if self._table is None:
            return

        # Clear existing rows
        self._table.clear()

        # Add rows for each column
        for col in file_info.columns:
            logical_type = col.logical_type or "-"
            self._table.add_row(
                col.name,
                col.physical_type,
                logical_type,
            )

        # Update header with column count
        header = self.query_one("#schema-header", Static)
        header.update(f"Schema ({len(file_info.columns)} columns)")

    def _apply_filter(self, filter_text: str) -> None:
        """Apply filter to the schema table.

        Args:
            filter_text: Filter text (column name or type)
        """
        if self._file_info is None or self._table is None:
            return

        filter_lower = filter_text.lower().strip()

        # Clear and repopulate with filtered results
        self._table.clear()

        filtered_count = 0
        for col in self._file_info.columns:
            # Check if filter matches column name or type
            if not filter_lower or (
                filter_lower in col.name.lower()
                or filter_lower in col.physical_type.lower()
                or (col.logical_type and filter_lower in col.logical_type.lower())
            ):
                logical_type = col.logical_type or "-"
                self._table.add_row(
                    col.name,
                    col.physical_type,
                    logical_type,
                )
                filtered_count += 1

        # Update header with filtered count
        header = self.query_one("#schema-header", Static)
        if filter_lower:
            total = len(self._file_info.columns)
            header.update(f"Schema ({filtered_count} of {total} columns)")
        else:
            header.update(f"Schema ({len(self._file_info.columns)} columns)")

    def clear(self) -> None:
        """Clear the schema view."""
        self._file_info = None

        if self._table:
            self._table.clear()

        if self._filter_input:
            self._filter_input.value = ""

        header = self.query_one("#schema-header", Static)
        header.update("Schema")

    def get_selected_column(self) -> str | None:
        """Get the currently selected column name.

        Returns:
            Selected column name or None if no selection
        """
        if self._table is None or self._file_info is None:
            return None

        cursor_row = self._table.cursor_row
        if cursor_row < 0:
            return None

        # Get the column name from the table
        try:
            row_data = self._table.get_row_at(cursor_row)
            return str(row_data[0])  # First column is the name
        except Exception:
            return None
