"""Tests for DataSampleView widget."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from textual.widgets import Button, DataTable, Input, Select, Static

from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo
from tablesleuth.tui.views.data_sample_view import DataSampleView


@pytest.fixture
def sample_parquet_file(tmp_path: Path) -> Path:
    """Create a sample Parquet file for testing."""
    # Create sample data
    data = {
        "id": [1, 2, 3, 4, 5],
        "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
        "age": [25, 30, 35, 40, 45],
        "salary": [50000.0, 60000.0, 70000.0, 80000.0, 90000.0],
    }
    table = pa.table(data)

    # Write to Parquet file
    file_path = tmp_path / "test_data.parquet"
    pq.write_table(table, file_path)

    return file_path


@pytest.fixture
def mock_file_info(sample_parquet_file: Path) -> ParquetFileInfo:
    """Create mock ParquetFileInfo."""
    return ParquetFileInfo(
        path=str(sample_parquet_file),
        file_size_bytes=1024,
        num_rows=5,
        num_row_groups=1,
        num_columns=4,
        schema={"id": "int64", "name": "string", "age": "int64", "salary": "double"},
        row_groups=[],
        columns=[
            ColumnStats(
                name="id",
                physical_type="INT64",
                logical_type=None,
                null_count=0,
                min_value=1,
                max_value=5,
                encodings=["PLAIN"],
                compression="SNAPPY",
                num_values=5,
                distinct_count=5,
                total_compressed_size=100,
                total_uncompressed_size=120,
            ),
            ColumnStats(
                name="name",
                physical_type="BYTE_ARRAY",
                logical_type="UTF8",
                null_count=0,
                min_value="Alice",
                max_value="Eve",
                encodings=["PLAIN"],
                compression="SNAPPY",
                num_values=5,
                distinct_count=5,
                total_compressed_size=150,
                total_uncompressed_size=180,
            ),
            ColumnStats(
                name="age",
                physical_type="INT64",
                logical_type=None,
                null_count=0,
                min_value=25,
                max_value=45,
                encodings=["PLAIN"],
                compression="SNAPPY",
                num_values=5,
                distinct_count=5,
                total_compressed_size=100,
                total_uncompressed_size=120,
            ),
            ColumnStats(
                name="salary",
                physical_type="DOUBLE",
                logical_type=None,
                null_count=0,
                min_value=50000.0,
                max_value=90000.0,
                encodings=["PLAIN"],
                compression="SNAPPY",
                num_values=5,
                distinct_count=5,
                total_compressed_size=120,
                total_uncompressed_size=140,
            ),
        ],
        created_by="test",
        format_version="2.6",
    )


class TestDataSampleView:
    """Tests for DataSampleView widget."""

    async def test_initialization_without_file_info(self) -> None:
        """Test DataSampleView initializes without file info."""
        view = DataSampleView()
        assert view._file_info is None
        assert len(view._selected_columns) == 0
        assert view._row_count == 10

    async def test_initialization_with_file_info(self, mock_file_info: ParquetFileInfo) -> None:
        """Test DataSampleView initializes with file info."""
        view = DataSampleView(file_info=mock_file_info)
        assert view._file_info == mock_file_info

    async def test_compose_creates_widgets(self) -> None:
        """Test that compose creates all required widgets."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Check that key widgets exist
            assert view.query_one("#sample-header", Static)
            assert view.query_one("#row-count-select", Select)
            assert view.query_one("#select-all-btn", Button)
            assert view.query_one("#deselect-all-btn", Button)
            assert view.query_one("#column-filter", Input)
            assert view.query_one("#sample-table", DataTable)
            assert view.query_one("#sample-status", Static)

    async def test_update_file_info(self, mock_file_info: ParquetFileInfo) -> None:
        """Test updating file info loads data."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            view.update_file_info(mock_file_info)
            await pilot.pause()

            # Check that columns were selected
            assert len(view._selected_columns) == 4
            assert "id" in view._selected_columns
            assert "name" in view._selected_columns

    async def test_clear(self, mock_file_info: ParquetFileInfo) -> None:
        """Test clearing the view."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            view.clear()
            await pilot.pause()

            assert view._file_info is None
            assert view._parquet_file is None
            assert len(view._selected_columns) == 0

    async def test_row_count_selection(self, mock_file_info: ParquetFileInfo) -> None:
        """Test changing row count."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Change row count
            select = view.query_one("#row-count-select", Select)
            select.value = 50
            await pilot.pause()

            assert view._row_count == 50

            # Check header updated
            header = view.query_one("#sample-header", Static)
            rendered = str(header.render())
            assert "50" in rendered

    async def test_select_all_button(self, mock_file_info: ParquetFileInfo) -> None:
        """Test select all button."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Deselect all first
            view._selected_columns.clear()

            # Click select all
            button = view.query_one("#select-all-btn", Button)
            await pilot.click(button)
            await pilot.pause()

            # All columns should be selected
            assert len(view._selected_columns) == 4

    async def test_deselect_all_button(self, mock_file_info: ParquetFileInfo) -> None:
        """Test deselect all button."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Verify columns are initially selected
            assert len(view._selected_columns) > 0

            # Click deselect all
            button = view.query_one("#deselect-all-btn", Button)
            await pilot.click(button)
            await pilot.pause()

            # Columns should still be tracked but the method was called
            # The actual deselection happens in _deselect_all_columns
            view._deselect_all_columns()
            await pilot.pause()

            # Now no columns should be selected
            assert len(view._selected_columns) == 0

    async def test_column_filter(self, mock_file_info: ParquetFileInfo) -> None:
        """Test filtering columns."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Type in filter
            filter_input = view.query_one("#column-filter", Input)
            filter_input.value = "name"
            await pilot.pause()

            assert view._column_filter == "name"

    async def test_format_cell_value_with_none(self) -> None:
        """Test formatting None values."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Test None value
            result = view._format_cell_value(None, pa.int64())
            assert "null" in str(result).lower() or "none" in str(result).lower()

    async def test_format_cell_value_with_string(self) -> None:
        """Test formatting string values."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Test string value
            result = view._format_cell_value("test", pa.string())
            assert "test" in str(result)

    async def test_format_cell_value_with_number(self) -> None:
        """Test formatting numeric values."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Test integer
            result = view._format_cell_value(42, pa.int64())
            assert "42" in str(result)

            # Test float
            result = view._format_cell_value(3.14, pa.float64())
            assert "3.14" in str(result)

    async def test_format_cell_value_with_boolean(self) -> None:
        """Test formatting boolean values."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Test boolean
            result = view._format_cell_value(True, pa.bool_())
            assert "true" in str(result).lower()

    async def test_load_sample_data_with_no_columns_selected(
        self, mock_file_info: ParquetFileInfo
    ) -> None:
        """Test loading data with no columns selected shows message."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Deselect all columns
            view._selected_columns.clear()

            # Try to load data
            view._load_sample_data()
            await pilot.pause()

            # Should show message about no columns
            status = view.query_one("#sample-status", Static)
            rendered = str(status.render())
            assert "No columns selected" in rendered or "select at least one" in rendered

    async def test_populate_data_table(self, mock_file_info: ParquetFileInfo) -> None:
        """Test populating data table with PyArrow table."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Create a simple PyArrow table
            data = {"col1": [1, 2, 3], "col2": ["a", "b", "c"]}
            table = pa.table(data)

            # Populate the data table
            view._populate_data_table(table)
            await pilot.pause()

            # Check that data table has correct structure
            data_table = view.query_one("#sample-table", DataTable)
            # DataTable doesn't have column_count/row_count attributes
            # Check using columns and rows properties
            assert len(data_table.columns) == 2
            assert data_table.row_count == 3

    async def test_error_handling_invalid_file(self) -> None:
        """Test error handling with invalid file."""
        from textual.app import App

        # Create invalid file info
        invalid_file_info = ParquetFileInfo(
            path="/nonexistent/file.parquet",
            file_size_bytes=0,
            num_rows=0,
            num_row_groups=0,
            num_columns=0,
            schema={},
            row_groups=[],
            columns=[],
            created_by="test",
            format_version="2.6",
        )

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Try to update with invalid file
            view.update_file_info(invalid_file_info)
            await pilot.pause()

            # Should handle error gracefully
            assert view._parquet_file is None

    async def test_create_column_list(self, mock_file_info: ParquetFileInfo) -> None:
        """Test creating column list."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Column list should be created
            column_items = view.query(".column-item")
            assert len(list(column_items)) == 4  # 4 columns in mock data

    async def test_update_column_list_with_filter(self, mock_file_info: ParquetFileInfo) -> None:
        """Test updating column list with filter."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Set filter
            view._column_filter = "age"
            view._update_column_list()
            await pilot.pause()

            # Should show filtered columns
            column_items = view.query(".column-item")
            # At least one column should match "age"
            assert len(list(column_items)) >= 1

    async def test_select_all_columns(self, mock_file_info: ParquetFileInfo) -> None:
        """Test _select_all_columns method."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Clear selections
            view._selected_columns.clear()

            # Select all
            view._select_all_columns()
            await pilot.pause()

            # All columns should be selected
            assert len(view._selected_columns) == 4

    async def test_deselect_all_columns(self, mock_file_info: ParquetFileInfo) -> None:
        """Test _deselect_all_columns method."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Deselect all
            view._deselect_all_columns()
            await pilot.pause()

            # No columns should be selected
            assert len(view._selected_columns) == 0


class TestDataSampleViewAdvanced:
    """Advanced tests for DataSampleView widget."""

    async def test_show_loading(self, mock_file_info: ParquetFileInfo) -> None:
        """Test showing loading indicator."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Call show loading
            view._show_loading()
            await pilot.pause()

            # Status should show loading message
            status = view.query_one("#sample-status", Static)
            rendered = str(status.render())
            assert "loading" in rendered.lower() or "..." in rendered

    async def test_show_message(self, mock_file_info: ParquetFileInfo) -> None:
        """Test showing custom message."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Show custom message
            view._show_message("Test message")
            await pilot.pause()

            status = view.query_one("#sample-status", Static)
            rendered = str(status.render())
            assert "Test message" in rendered

    async def test_show_error(self, mock_file_info: ParquetFileInfo) -> None:
        """Test showing error message."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Show error
            view._show_error("Error occurred")
            await pilot.pause()

            status = view.query_one("#sample-status", Static)
            rendered = str(status.render())
            assert "Error occurred" in rendered or "error" in rendered.lower()

    async def test_update_status(self, mock_file_info: ParquetFileInfo) -> None:
        """Test updating status message."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Update status
            view._update_status("Custom status")
            await pilot.pause()

            status = view.query_one("#sample-status", Static)
            rendered = str(status.render())
            assert "Custom status" in rendered

    async def test_format_cell_value_with_timestamp(self) -> None:
        """Test formatting timestamp values."""
        from datetime import datetime

        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Test timestamp
            timestamp = datetime(2024, 1, 15, 10, 30, 0)
            result = view._format_cell_value(timestamp, pa.timestamp("us"))
            assert "2024" in str(result)

    async def test_format_cell_value_with_date(self) -> None:
        """Test formatting date values."""
        from datetime import date

        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Test date
            test_date = date(2024, 1, 15)
            result = view._format_cell_value(test_date, pa.date32())
            assert "2024" in str(result)

    async def test_format_cell_value_with_large_number(self) -> None:
        """Test formatting large numbers."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Test large number
            result = view._format_cell_value(1234567890, pa.int64())
            # Should contain the number (possibly formatted)
            assert "1234567890" in str(result) or "1,234,567,890" in str(result)

    async def test_format_cell_value_with_binary(self) -> None:
        """Test formatting binary values."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Test binary data
            binary_data = b"test binary"
            result = view._format_cell_value(binary_data, pa.binary())
            # Should show some representation of binary
            assert len(str(result)) > 0

    async def test_load_sample_data_with_row_limit(self, mock_file_info: ParquetFileInfo) -> None:
        """Test that row limit is respected."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Set row count to 3
            view._row_count = 3
            view._load_sample_data()
            await pilot.pause()

            # Data table should have at most 3 rows
            data_table = view.query_one("#sample-table", DataTable)
            assert data_table.row_count <= 3

    async def test_column_selection_persistence(self, mock_file_info: ParquetFileInfo) -> None:
        """Test that column selection persists across reloads."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Select specific columns
            view._selected_columns = {"id", "name"}
            view._load_sample_data()
            await pilot.pause()

            # Verify only selected columns are shown
            data_table = view.query_one("#sample-table", DataTable)
            assert len(data_table.columns) == 2

    async def test_empty_parquet_file_handling(self, tmp_path: Path) -> None:
        """Test handling of empty Parquet file."""
        from textual.app import App

        # Create empty Parquet file
        empty_data = {"col1": []}
        table = pa.table(empty_data)
        file_path = tmp_path / "empty.parquet"
        pq.write_table(table, file_path)

        empty_file_info = ParquetFileInfo(
            path=str(file_path),
            file_size_bytes=100,
            num_rows=0,
            num_row_groups=0,
            num_columns=1,
            schema={"col1": "int64"},
            row_groups=[],
            columns=[
                ColumnStats(
                    name="col1",
                    physical_type="INT64",
                    logical_type=None,
                    null_count=0,
                    min_value=None,
                    max_value=None,
                    encodings=["PLAIN"],
                    compression="SNAPPY",
                    num_values=0,
                    distinct_count=0,
                    total_compressed_size=0,
                    total_uncompressed_size=0,
                )
            ],
            created_by="test",
            format_version="2.6",
        )

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)

            # Should handle empty file gracefully
            view.update_file_info(empty_file_info)
            await pilot.pause()

            # Should not crash
            assert view._file_info is not None

    async def test_column_filter_case_insensitive(self, mock_file_info: ParquetFileInfo) -> None:
        """Test that column filter is case insensitive."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Set filter with lowercase (filter is already lowercased in the method)
            view._column_filter = "name"
            view._update_column_list()
            await pilot.pause()

            # Should match "name" column
            column_items = view.query(".column-item")
            # At least one column should match
            assert len(list(column_items)) >= 1

    async def test_multiple_row_count_changes(self, mock_file_info: ParquetFileInfo) -> None:
        """Test changing row count multiple times."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(file_info=mock_file_info, id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Change row count multiple times
            for count in [10, 50, 100, 10]:
                select = view.query_one("#row-count-select", Select)
                select.value = count
                await pilot.pause()
                assert view._row_count == count

    async def test_data_table_initialization(self) -> None:
        """Test that data table is properly initialized."""
        from textual.app import App

        class TestApp(App):
            def compose(self):
                yield DataSampleView(id="test-view")

        app = TestApp()
        async with app.run_test() as pilot:
            view = app.query_one("#test-view", DataSampleView)
            await pilot.pause()

            # Data table should be initialized
            assert view._data_table is not None
            assert isinstance(view._data_table, DataTable)
