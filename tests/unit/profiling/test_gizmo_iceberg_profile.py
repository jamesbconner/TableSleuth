"""Tests for Iceberg table profiling via GizmoDuckDB.

Verifies that profile_single_column correctly uses registered Iceberg tables
by calling _replace_iceberg_tables to generate iceberg_scan() calls.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler


@pytest.fixture
def profiler():
    """Create a GizmoDuckDbProfiler instance."""
    return GizmoDuckDbProfiler(
        uri="motherduck://test_db",
        username="test_user",
        password="test_pass",
        tls_skip_verify=True,
    )


def test_profile_single_column_uses_iceberg_registration(profiler):
    """Test that profile_single_column uses registered Iceberg tables."""
    # Register an Iceberg table
    table_id = "my_iceberg_table"
    metadata_loc = "/path/to/metadata.json"
    snapshot_id = 12345

    profiler.register_iceberg_table_with_snapshot(table_id, metadata_loc, snapshot_id)

    # Mock the connection to verify the generated SQL
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    # First query checks column type
    mock_cursor.fetchone.side_effect = [
        ("INTEGER",),  # Type check result
        (100, 95, 5, 50, 1, 100, 50.5, 50, 25, 75, 28.87, 833.33),  # Stats result
        (42, 10),  # Mode result
    ]

    with patch.object(profiler, "_connect", return_value=mock_conn):
        result = profiler.profile_single_column(table_id, "my_column")

    # Verify that iceberg_scan was used in the SQL queries (type check, stats, mode).
    # INSTALL/LOAD iceberg run first per connection block, so filter to profiling queries only.
    calls = mock_cursor.execute.call_args_list
    iceberg_queries = [call[0][0] for call in calls if "iceberg_scan" in call[0][0]]
    assert len(iceberg_queries) == 3, f"Expected 3 iceberg_scan queries, got {len(iceberg_queries)}"

    for sql in iceberg_queries:
        assert metadata_loc.replace("'", "''") in sql
        assert f"version => {snapshot_id}" in sql


def test_profile_single_column_uses_delta_registration(profiler):
    """Test that profile_single_column uses registered Delta tables."""
    # Register a Delta table
    table_id = "my_delta_table"
    file_uris = ["/path/to/file1.parquet", "/path/to/file2.parquet"]

    # Manually set up Delta table registration (since we don't have the full method here)
    profiler._delta_tables[table_id] = file_uris

    # Mock the connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    mock_cursor.fetchone.side_effect = [
        ("VARCHAR",),  # Type check result
        (100, 95, 5, 50, "a", "z"),  # Stats result (non-numeric)
        ("mode_val", 10),  # Mode result
    ]

    with patch.object(profiler, "_connect", return_value=mock_conn):
        result = profiler.profile_single_column(table_id, "my_column")

    # Verify that read_parquet was used with the file URIs
    calls = mock_cursor.execute.call_args_list
    assert len(calls) == 3

    for call in calls:
        sql = call[0][0]
        assert "read_parquet" in sql
        # Check that file URIs are present
        assert any(uri.replace("'", "''") in sql for uri in file_uris)


def test_profile_single_column_fallback_to_bare_table_name(profiler):
    """Test that profile_single_column falls back to bare table name when no registration exists."""
    table_name = "regular_table"

    # Mock the connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    mock_cursor.fetchone.side_effect = [
        ("INTEGER",),
        (100, 95, 5, 50, 1, 100, 50.5, 50, 25, 75, 28.87, 833.33),
        (42, 10),
    ]

    with patch.object(profiler, "_connect", return_value=mock_conn):
        result = profiler.profile_single_column(table_name, "my_column")

    # Verify that the bare table name is used (no scan functions)
    calls = mock_cursor.execute.call_args_list
    for call in calls:
        sql = call[0][0]
        assert "iceberg_scan" not in sql
        assert table_name in sql


def test_profile_single_column_with_view_paths(profiler):
    """Test that profile_single_column prefers _view_paths over Iceberg registration."""
    view_name = "my_view"
    file_paths = ["/path/to/file.parquet"]

    # Set up view paths
    profiler._view_paths = {view_name: file_paths}

    # Also register as Iceberg (should be ignored in favor of _view_paths)
    profiler.register_iceberg_table_with_snapshot(view_name, "/metadata.json", 123)

    # Mock the connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    mock_cursor.fetchone.side_effect = [
        ("INTEGER",),
        (100, 95, 5, 50, 1, 100, 50.5, 50, 25, 75, 28.87, 833.33),
        (42, 10),
    ]

    with patch.object(profiler, "_connect", return_value=mock_conn):
        result = profiler.profile_single_column(view_name, "my_column")

    # Verify that read_parquet with view paths is used, NOT iceberg_scan
    calls = mock_cursor.execute.call_args_list
    for call in calls:
        sql = call[0][0]
        assert "read_parquet" in sql
        assert "iceberg_scan" not in sql
        assert file_paths[0].replace("'", "''") in sql


def test_profile_columns_uses_iceberg_registration(profiler):
    """Test that profile_columns correctly delegates to profile_single_column with Iceberg tables."""
    table_id = "iceberg_table"
    profiler.register_iceberg_table_with_snapshot(table_id, "/metadata.json", 999)

    # Mock the connection
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    # Return results for two columns
    mock_cursor.fetchone.side_effect = [
        # Column 1
        ("INTEGER",),
        (100, 95, 5, 50, 1, 100, 50.5, 50, 25, 75, 28.87, 833.33),
        (42, 10),
        # Column 2
        ("VARCHAR",),
        (100, 90, 10, 40, "a", "z"),
        ("mode", 5),
    ]

    with patch.object(profiler, "_connect", return_value=mock_conn):
        results = profiler.profile_columns(table_id, ["col1", "col2"])

    assert len(results) == 2
    assert "col1" in results
    assert "col2" in results

    # Verify iceberg_scan was used in profiling queries (INSTALL/LOAD run first per block)
    calls = mock_cursor.execute.call_args_list
    iceberg_queries = [call[0][0] for call in calls if "iceberg_scan" in call[0][0]]
    assert (
        len(iceberg_queries) >= 3
    ), f"Expected at least 3 iceberg_scan queries, got {len(iceberg_queries)}"
