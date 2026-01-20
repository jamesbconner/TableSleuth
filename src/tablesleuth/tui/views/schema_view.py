"""Schema view widget for displaying Parquet file schema."""

from __future__ import annotations

import logging
from pathlib import Path

from pyarrow.parquet import ParquetFile
from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, Input, Static

from tablesleuth.models.parquet import ParquetFileInfo
from tablesleuth.utils.path_utils import is_s3_path

logger = logging.getLogger(__name__)


class SchemaView(Container):
    """Widget for displaying Parquet file schema with detailed column information.

    Displays columns in a DataTable with:
    - Column name
    - Physical type
    - Logical type

    When a column is selected, displays comprehensive metadata in a detail panel:
    - Type information
    - Schema structure (definition/repetition levels)
    - Compression and encoding
    - Statistics
    - Size information
    - Page information

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

    SchemaView #schema-content {
        height: 1fr;
    }

    SchemaView #schema-table-container {
        width: 40%;
        border-right: solid $accent;
    }

    SchemaView #schema-detail-container {
        width: 60%;
        padding: 1;
    }

    SchemaView Input {
        margin: 0 1;
        border: solid $accent;
    }

    SchemaView DataTable {
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
        self._parquet_file: ParquetFile | None = None

    def compose(self) -> ComposeResult:
        """Compose the schema view."""
        yield Static("Schema", id="schema-header")

        with Horizontal(id="schema-content"):
            # Left side: Table with filter
            with Vertical(id="schema-table-container"):
                yield Input(placeholder="Filter columns...", id="schema-filter")
                yield DataTable(id="schema-table", cursor_type="row")

            # Right side: Detail panel
            with VerticalScroll(id="schema-detail-container"):
                yield Static(id="schema-detail-panel")

    def on_mount(self) -> None:
        """Set up the view when mounted."""
        self._table = self.query_one("#schema-table", DataTable)
        self._filter_input = self.query_one("#schema-filter", Input)

        # Add columns
        self._table.add_columns("Column", "Physical Type", "Logical Type")

        # Initialize detail panel with prompt message
        detail_panel = self.query_one("#schema-detail-panel", Static)
        detail_panel.update(
            Panel(
                Text("Select a column to view details", style="dim italic"),
                title="Column Details",
                border_style="dim",
            )
        )

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

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row selection in the schema table.

        Args:
            event: Row highlighted event
        """
        # Get the selected column name
        column_name = self.get_selected_column()

        if column_name:
            # Create and display the detail panel
            panel = self._create_column_detail_panel(column_name)
            detail_static = self.query_one("#schema-detail-panel", Static)
            detail_static.update(panel)

    def update_schema(self, file_info: ParquetFileInfo) -> None:
        """Update the displayed schema.

        Args:
            file_info: ParquetFileInfo with schema information
        """
        self._file_info = file_info

        # Load PyArrow ParquetFile for detailed metadata access (with S3 support)
        try:
            from tablesleuth.services.filesystem import FileSystem

            fs = FileSystem()
            if is_s3_path(file_info.path):
                filesystem = fs.get_filesystem(file_info.path)
                normalized_path = fs.normalize_s3_path(file_info.path)
                self._parquet_file = ParquetFile(normalized_path, filesystem=filesystem)
            else:
                self._parquet_file = ParquetFile(file_info.path)
        except Exception as e:
            logger.debug(f"Could not load ParquetFile for detailed metadata: {e}")
            self._parquet_file = None

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
        self._parquet_file = None

        if self._table:
            self._table.clear()

        if self._filter_input:
            self._filter_input.value = ""

        header = self.query_one("#schema-header", Static)
        header.update("Schema")

        # Reset detail panel
        detail_panel = self.query_one("#schema-detail-panel", Static)
        detail_panel.update(
            Panel(
                Text("Select a column to view details", style="dim italic"),
                title="Column Details",
                border_style="dim",
            )
        )

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

    def _create_column_detail_panel(self, column_name: str) -> Panel:
        """Create a Rich Panel with comprehensive column metadata.

        Args:
            column_name: Name of the column to display details for

        Returns:
            Rich Panel with formatted column metadata
        """
        if self._file_info is None:
            return Panel(
                Text("No file loaded", style="dim italic"),
                title="Column Details",
                border_style="dim",
            )

        # Find the column in file_info
        col = next((c for c in self._file_info.columns if c.name == column_name), None)
        if col is None:
            return Panel(
                Text("Column not found", style="dim italic"),
                title="Column Details",
                border_style="dim",
            )

        # Build the panel content
        content = Text()

        # TYPE INFORMATION section
        content.append("TYPE INFORMATION\n", style="bold cyan")
        content.append("  Physical Type: ", style="dim")
        content.append(f"{col.physical_type}\n", style="green")

        content.append("  Logical Type: ", style="dim")
        if col.logical_type:
            content.append(f"{col.logical_type}\n", style="green")
        else:
            content.append("None\n", style="dim")

        content.append("  Nullable: ", style="dim")
        is_nullable = self._is_nullable(column_name)
        content.append("Yes\n" if is_nullable else "No\n")
        content.append("\n")

        # SCHEMA STRUCTURE section
        content.append("SCHEMA STRUCTURE\n", style="bold cyan")
        max_def, max_rep = self._get_schema_levels(column_name)

        content.append("  Max Definition Level: ", style="dim")
        content.append(f"{max_def} ", style="yellow")
        def_explanation = self._explain_definition_level(max_def)
        content.append(f"({def_explanation})\n", style="dim italic")

        content.append("  Max Repetition Level: ", style="dim")
        content.append(f"{max_rep} ", style="yellow")
        rep_explanation = self._explain_repetition_level(max_rep)
        content.append(f"({rep_explanation})\n", style="dim italic")
        content.append("\n")

        # COMPRESSION & ENCODING section
        content.append("COMPRESSION & ENCODING\n", style="bold cyan")
        content.append("  Codec: ", style="dim")
        codec_style = "green" if col.compression != "UNCOMPRESSED" else "yellow"
        content.append(f"{col.compression}\n", style=codec_style)

        content.append("  Encodings: ", style="dim")
        encodings_str = ", ".join(col.encodings) if col.encodings else "None"
        content.append(f"{encodings_str}\n")

        content.append("  Dictionary: ", style="dim")
        has_dict = self._has_dictionary_encoding(column_name)
        content.append("Yes\n" if has_dict else "No\n", style="green" if has_dict else "dim")
        content.append("\n")

        # STATISTICS section
        content.append("STATISTICS\n", style="bold cyan")

        content.append("  Values: ", style="dim")
        if col.num_values is not None:
            content.append(f"{col.num_values:,}\n")
        else:
            content.append("N/A\n", style="dim")

        content.append("  Nulls: ", style="dim")
        if col.null_count is not None:
            null_style = "red" if col.null_count > 0 else "green"
            content.append(f"{col.null_count:,}\n", style=null_style)
        else:
            content.append("N/A\n", style="dim")

        content.append("  Distinct: ", style="dim")
        if col.distinct_count is not None:
            content.append(f"{col.distinct_count:,}\n")
        else:
            content.append("N/A\n", style="dim")

        if col.min_value is not None and col.max_value is not None:
            min_str = str(col.min_value)[:40]
            max_str = str(col.max_value)[:40]
            content.append("  Min: ", style="dim")
            content.append(f"{min_str}\n", style="cyan")
            content.append("  Max: ", style="dim")
            content.append(f"{max_str}\n", style="cyan")
        content.append("\n")

        # SIZE INFORMATION section
        if col.total_compressed_size is not None and col.total_uncompressed_size is not None:
            content.append("SIZE INFORMATION\n", style="bold cyan")

            content.append("  Compressed: ", style="dim")
            content.append(f"{self._format_size(col.total_compressed_size)}\n")

            content.append("  Uncompressed: ", style="dim")
            content.append(f"{self._format_size(col.total_uncompressed_size)}\n")

            ratio, ratio_color = self._calculate_compression_ratio(
                col.total_compressed_size, col.total_uncompressed_size
            )
            if ratio is not None:
                content.append("  Ratio: ", style="dim")
                content.append(f"{ratio:.1f}%\n", style=ratio_color)
            content.append("\n")

        # PAGE INFORMATION section
        page_info = self._get_page_information(column_name)
        if page_info:
            content.append("PAGE INFORMATION\n", style="bold cyan")

            if page_info.get("has_dictionary_page"):
                content.append("  Dictionary Page: ", style="dim")
                content.append("Yes ", style="green")
                if page_info.get("dictionary_page_offset") is not None:
                    content.append(
                        f"(offset: {page_info['dictionary_page_offset']:,})\n", style="dim"
                    )
                else:
                    content.append("\n")

            if page_info.get("data_page_offset") is not None:
                content.append("  Data Page Offset: ", style="dim")
                content.append(f"{page_info['data_page_offset']:,}\n")

            content.append("  Column Index: ", style="dim")
            has_col_idx = page_info.get("has_column_index", False)
            content.append(
                "Yes\n" if has_col_idx else "No\n", style="green" if has_col_idx else "dim"
            )

            content.append("  Offset Index: ", style="dim")
            has_off_idx = page_info.get("has_offset_index", False)
            content.append(
                "Yes\n" if has_off_idx else "No\n", style="green" if has_off_idx else "dim"
            )

        return Panel(
            content,
            title=f"[bold cyan]{column_name}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )

    def _get_schema_levels(self, column_name: str) -> tuple[int, int]:
        """Get max definition and repetition levels for a column.

        Args:
            column_name: Name of the column

        Returns:
            Tuple of (max_definition_level, max_repetition_level)
        """
        if self._parquet_file is None:
            return (1, 0)  # Default: nullable, scalar

        try:
            schema = self._parquet_file.schema
            # Find column index
            col_idx = None
            for i in range(schema.num_columns):
                if schema.column(i).name == column_name:
                    col_idx = i
                    break

            if col_idx is not None:
                col_schema = schema.column(col_idx)
                return (col_schema.max_definition_level, col_schema.max_repetition_level)
        except Exception as e:
            logger.debug(f"Could not get schema levels for {column_name}: {e}")

        return (1, 0)  # Default

    @staticmethod
    def _explain_definition_level(level: int) -> str:
        """Explain what a definition level means.

        Args:
            level: Definition level

        Returns:
            Human-readable explanation
        """
        if level == 0:
            return "required, not nullable"
        elif level == 1:
            return "nullable column"
        else:
            return f"nested optional fields, depth {level}"

    @staticmethod
    def _explain_repetition_level(level: int) -> str:
        """Explain what a repetition level means.

        Args:
            level: Repetition level

        Returns:
            Human-readable explanation
        """
        if level == 0:
            return "scalar, not repeated"
        elif level == 1:
            return "array/list"
        else:
            return f"nested arrays, depth {level}"

    def _is_nullable(self, column_name: str) -> bool:
        """Check if a column is nullable.

        Args:
            column_name: Name of the column

        Returns:
            True if column is nullable, False otherwise
        """
        max_def, _ = self._get_schema_levels(column_name)
        return max_def > 0

    def _has_dictionary_encoding(self, column_name: str) -> bool:
        """Check if a column uses dictionary encoding.

        Args:
            column_name: Name of the column

        Returns:
            True if column uses dictionary encoding, False otherwise
        """
        if self._file_info is None:
            return False

        col = next((c for c in self._file_info.columns if c.name == column_name), None)
        if col is None or not col.encodings:
            return False

        # Check for dictionary-related encodings
        dict_encodings = {"RLE_DICTIONARY", "DICTIONARY", "PLAIN_DICTIONARY"}
        return any(enc in dict_encodings for enc in col.encodings)

    def _get_page_information(self, column_name: str) -> dict | None:
        """Get page-level information for a column from first row group.

        Args:
            column_name: Name of the column

        Returns:
            Dict with page information or None if unavailable
        """
        if self._parquet_file is None:
            return None

        try:
            md = self._parquet_file.metadata
            if md.num_row_groups == 0:
                return None

            # Get first row group
            rg = md.row_group(0)

            # Find column by name
            for i in range(rg.num_columns):
                col = rg.column(i)
                if col.path_in_schema == column_name:
                    return {
                        "has_dictionary_page": col.has_dictionary_page,
                        "dictionary_page_offset": col.dictionary_page_offset
                        if col.has_dictionary_page
                        else None,
                        "data_page_offset": col.data_page_offset,
                        "has_column_index": col.has_column_index,
                        "has_offset_index": col.has_offset_index,
                    }
        except Exception as e:
            logger.debug(f"Could not get page information for {column_name}: {e}")

        return None

    @staticmethod
    def _format_size(size_bytes: int | None) -> str:
        """Format byte size to human-readable format.

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
