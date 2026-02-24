"""Tests for Delta table registration with storage options."""

from unittest.mock import MagicMock, patch

import pytest

from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler


class TestDeltaStorageOptions:
    """Tests for register_delta_table_with_version with storage_options."""

    @patch("deltalake.DeltaTable")
    def test_register_delta_without_storage_options(self, mock_delta_table: MagicMock) -> None:
        """Test registering Delta table without storage options."""
        mock_dt = MagicMock()
        mock_dt.file_uris.return_value = ["s3://bucket/file1.parquet", "s3://bucket/file2.parquet"]
        mock_dt.get_add_actions.return_value.column.return_value.to_pylist.return_value = [
            100,
            200,
        ]
        mock_delta_table.return_value = mock_dt

        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )
        profiler.register_delta_table_with_version("test_table", "/path/to/delta", version=1)

        # Verify DeltaTable was called with correct arguments
        mock_delta_table.assert_called_once_with("/path/to/delta", version=1)
        assert "test_table" in profiler._delta_tables
        assert len(profiler._delta_tables["test_table"]) == 2

    @patch("deltalake.DeltaTable")
    def test_register_delta_with_storage_options(self, mock_delta_table: MagicMock) -> None:
        """Test registering Delta table with storage options."""
        mock_dt = MagicMock()
        mock_dt.file_uris.return_value = ["s3://bucket/file1.parquet"]
        mock_dt.get_add_actions.return_value.column.return_value.to_pylist.return_value = [100]
        mock_delta_table.return_value = mock_dt

        storage_opts = {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-west-2",
        }

        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )
        profiler.register_delta_table_with_version(
            "test_table", "s3://bucket/delta", version=2, storage_options=storage_opts
        )

        # Verify DeltaTable was called with storage_options
        mock_delta_table.assert_called_once_with(
            "s3://bucket/delta", version=2, storage_options=storage_opts
        )
        assert "test_table" in profiler._delta_tables

    @patch("deltalake.DeltaTable")
    def test_register_delta_latest_version_with_storage_options(
        self, mock_delta_table: MagicMock
    ) -> None:
        """Test registering Delta table at latest version with storage options."""
        mock_dt = MagicMock()
        mock_dt.file_uris.return_value = ["s3://bucket/file1.parquet"]
        mock_dt.get_add_actions.return_value.column.return_value.to_pylist.return_value = [100]
        mock_delta_table.return_value = mock_dt

        storage_opts = {"AWS_REGION": "eu-west-1"}

        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )
        profiler.register_delta_table_with_version(
            "test_table", "s3://bucket/delta", storage_options=storage_opts
        )

        # Verify DeltaTable was called without version but with storage_options
        mock_delta_table.assert_called_once_with("s3://bucket/delta", storage_options=storage_opts)
        assert "test_table" in profiler._delta_tables

    @patch("deltalake.DeltaTable")
    def test_register_delta_collects_stats(self, mock_delta_table: MagicMock) -> None:
        """Test that stats are collected from Delta table."""
        mock_dt = MagicMock()
        mock_dt.file_uris.return_value = ["file1.parquet", "file2.parquet", "file3.parquet"]

        # Mock get_add_actions to return stats
        mock_actions = MagicMock()
        mock_actions.column.side_effect = lambda col: (
            MagicMock(to_pylist=lambda: [1000, 2000, 3000])
            if col == "size_bytes"
            else MagicMock(to_pylist=lambda: [100, 200, 300])
        )
        mock_dt.get_add_actions.return_value = mock_actions
        mock_delta_table.return_value = mock_dt

        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:31337", username="test", password="test"
        )
        profiler.register_delta_table_with_version("test_table", "/path/to/delta", version=5)

        # Verify stats were collected
        assert "test_table" in profiler._delta_table_stats
        file_count, total_bytes, total_rows = profiler._delta_table_stats["test_table"]
        assert file_count == 3
        assert total_bytes == 6000  # 1000 + 2000 + 3000
        assert total_rows == 600  # 100 + 200 + 300
