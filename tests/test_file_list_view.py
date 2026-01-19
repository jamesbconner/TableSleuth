"""Tests for FileListView widget."""

from __future__ import annotations

import pytest

from tablesleuth.models.file_ref import FileRef
from tablesleuth.tui.views.file_list_view import FileListView


class TestFileListView:
    """Tests for FileListView widget."""

    def test_update_files_strips_s3_prefix(self):
        """Test that s3:// prefix is stripped from display paths."""
        files = [
            FileRef(
                path="s3://bucket/path/to/file.parquet",
                file_size_bytes=1024,
                record_count=100,
                source="s3",
            )
        ]

        view = FileListView(files=files)
        # Simulate mounting to initialize table
        view._table = MockDataTable()
        view.update_files(files)

        # Verify s3:// prefix was stripped
        assert len(view._table.rows) == 1
        display_path = view._table.rows[0][0]
        assert not display_path.startswith("s3://")
        assert display_path.startswith("bucket/")

    def test_update_files_strips_s3a_prefix(self):
        """Test that s3a:// prefix is stripped from display paths."""
        files = [
            FileRef(
                path="s3a://bucket/path/to/file.parquet",
                file_size_bytes=2048,
                record_count=200,
                source="s3",
            )
        ]

        view = FileListView(files=files)
        # Simulate mounting to initialize table
        view._table = MockDataTable()
        view.update_files(files)

        # Verify s3a:// prefix was stripped
        assert len(view._table.rows) == 1
        display_path = view._table.rows[0][0]
        assert not display_path.startswith("s3a://")
        assert display_path.startswith("bucket/")

    def test_update_files_handles_mixed_s3_schemes(self):
        """Test that both s3:// and s3a:// schemes are handled consistently."""
        files = [
            FileRef(
                path="s3://bucket1/file1.parquet",
                file_size_bytes=1024,
                record_count=100,
                source="s3",
            ),
            FileRef(
                path="s3a://bucket2/file2.parquet",
                file_size_bytes=2048,
                record_count=200,
                source="s3",
            ),
        ]

        view = FileListView(files=files)
        # Simulate mounting to initialize table
        view._table = MockDataTable()
        view.update_files(files)

        # Verify both prefixes were stripped
        assert len(view._table.rows) == 2
        assert view._table.rows[0][0].startswith("bucket1/")
        assert view._table.rows[1][0].startswith("bucket2/")
        assert not view._table.rows[0][0].startswith("s3://")
        assert not view._table.rows[1][0].startswith("s3a://")

    def test_update_files_truncates_long_paths(self):
        """Test that long paths are truncated to last 4 segments."""
        files = [
            FileRef(
                path="s3://bucket/warehouse/db/table/partition1/partition2/file.parquet",
                file_size_bytes=1024,
                record_count=100,
                source="s3",
            )
        ]

        view = FileListView(files=files)
        # Simulate mounting to initialize table
        view._table = MockDataTable()
        view.update_files(files)

        # Verify path was truncated to last 4 segments
        assert len(view._table.rows) == 1
        display_path = view._table.rows[0][0]
        path_parts = display_path.split("/")
        assert len(path_parts) == 4
        assert display_path == "table/partition1/partition2/file.parquet"

    def test_update_files_preserves_local_paths(self):
        """Test that local paths are not modified."""
        files = [
            FileRef(
                path="/local/path/to/file.parquet",
                file_size_bytes=1024,
                record_count=100,
                source="directory",
            )
        ]

        view = FileListView(files=files)
        # Simulate mounting to initialize table
        view._table = MockDataTable()
        view.update_files(files)

        # Verify local path handling
        assert len(view._table.rows) == 1
        display_path = view._table.rows[0][0]
        # Should be truncated to last 4 segments but not have s3:// stripped
        assert "file.parquet" in display_path


class MockDataTable:
    """Mock DataTable for testing without Textual app context."""

    def __init__(self):
        """Initialize mock table."""
        self.rows = []
        self.columns = []

    def clear(self):
        """Clear all rows."""
        self.rows = []

    def add_columns(self, *columns):
        """Add columns."""
        self.columns = list(columns)

    def add_row(self, *values):
        """Add a row."""
        self.rows.append(values)
