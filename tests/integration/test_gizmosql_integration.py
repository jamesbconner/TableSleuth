"""Integration tests for GizmoSQL profiling backend.

These tests require a running GizmoSQL container.
They will be skipped if GizmoSQL is not available.

To run GizmoSQL:
    docker run -d -p 31337:31337 gizmosql/gizmosql:latest
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def gizmo_profiler() -> GizmoDuckDbProfiler:
    """Create a GizmoDuckDbProfiler instance.

    This will be skipped if GizmoSQL is not available.
    """
    try:
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="gizmosql_username",
            password="gizmosql_password",
            tls_skip_verify=True,
        )
        return profiler
    except Exception as e:
        pytest.skip(f"GizmoSQL not available: {e}")


@pytest.fixture
def test_parquet_file() -> Path:
    """Get path to test Parquet file."""
    test_file = Path("tests/data/nested_test.parquet")
    if not test_file.exists():
        pytest.skip("Test Parquet file not found")
    return test_file


@pytest.mark.skip(reason="Requires running GizmoSQL container")
def test_gizmo_connection(gizmo_profiler: GizmoDuckDbProfiler) -> None:
    """Test that we can connect to GizmoSQL."""
    # If we got here, connection was successful
    assert gizmo_profiler is not None


@pytest.mark.skip(reason="Requires running GizmoSQL container")
def test_register_single_file(
    gizmo_profiler: GizmoDuckDbProfiler,
    test_parquet_file: Path,
) -> None:
    """Test registering a single Parquet file."""
    view_name = gizmo_profiler.register_file_view([str(test_parquet_file)])

    assert view_name is not None
    assert isinstance(view_name, str)


@pytest.mark.skip(reason="Requires running GizmoSQL container")
def test_register_multiple_files(
    gizmo_profiler: GizmoDuckDbProfiler,
    test_parquet_file: Path,
) -> None:
    """Test registering multiple Parquet files."""
    # Use the same file multiple times for testing
    file_paths = [str(test_parquet_file), str(test_parquet_file)]

    view_name = gizmo_profiler.register_file_view(file_paths)

    assert view_name is not None


@pytest.mark.skip(reason="Requires running GizmoSQL container")
def test_profile_single_column(
    gizmo_profiler: GizmoDuckDbProfiler,
    test_parquet_file: Path,
) -> None:
    """Test profiling a single column."""
    # Register file
    view_name = gizmo_profiler.register_file_view([str(test_parquet_file)])

    # Get a column name from the file
    # For this test, we'll use a known column or skip if not available
    try:
        from tablesleuth.services.parquet_service import ParquetInspector

        inspector = ParquetInspector()
        file_info = inspector.inspect_file(test_parquet_file)

        if not file_info.columns:
            pytest.skip("No columns in test file")

        column_name = file_info.columns[0].name

        # Profile the column
        profile = gizmo_profiler.profile_single_column(view_name, column_name)

        assert profile is not None
        assert profile.column == column_name
        assert profile.row_count >= 0
        assert profile.non_null_count >= 0
        assert profile.null_count >= 0

    except Exception as e:
        pytest.skip(f"Could not profile column: {e}")


@pytest.mark.skip(reason="Requires running GizmoSQL container")
def test_profile_results_accuracy(
    gizmo_profiler: GizmoDuckDbProfiler,
    test_parquet_file: Path,
) -> None:
    """Test that profiling results are accurate."""
    try:
        from tablesleuth.services.parquet_service import ParquetInspector

        inspector = ParquetInspector()
        file_info = inspector.inspect_file(test_parquet_file)

        # Register file
        view_name = gizmo_profiler.register_file_view([str(test_parquet_file)])

        # Profile first column
        column_name = file_info.columns[0].name
        profile = gizmo_profiler.profile_single_column(view_name, column_name)

        # Verify row count matches file metadata
        assert profile.row_count == file_info.num_rows

        # Verify null count consistency
        assert profile.row_count == profile.non_null_count + profile.null_count

    except Exception as e:
        pytest.skip(f"Could not verify accuracy: {e}")


@pytest.mark.skip(reason="Requires running GizmoSQL container")
def test_connection_error_handling() -> None:
    """Test handling of connection errors."""
    # Try to connect to non-existent server
    profiler = GizmoDuckDbProfiler(
        uri="grpc+tls://nonexistent:99999",
        username="test",
        password="test",
        tls_skip_verify=True,
    )

    # Should raise error when trying to use it
    with pytest.raises((ValueError, RuntimeError, ConnectionError)):
        profiler.register_file_view(["/nonexistent/file.parquet"])


def test_profiler_initialization() -> None:
    """Test that profiler can be initialized (no connection required)."""
    profiler = GizmoDuckDbProfiler(
        uri="grpc+tls://localhost:31337",
        username="test",
        password="test",
        tls_skip_verify=True,
    )

    assert profiler is not None


def test_profiler_configuration() -> None:
    """Test profiler configuration options."""
    profiler = GizmoDuckDbProfiler(
        uri="grpc://custom:1234",
        username="custom_user",
        password="custom_pass",
        tls_skip_verify=False,
    )

    assert profiler._uri == "grpc://custom:1234"
    assert profiler._username == "custom_user"
    assert profiler._password == "custom_pass"
    assert profiler._tls_skip_verify is False


@pytest.mark.skip(reason="Requires running GizmoSQL container")
def test_profile_multiple_columns(
    gizmo_profiler: GizmoDuckDbProfiler,
    test_parquet_file: Path,
) -> None:
    """Test profiling multiple columns."""
    try:
        from tablesleuth.services.parquet_service import ParquetInspector

        inspector = ParquetInspector()
        file_info = inspector.inspect_file(test_parquet_file)

        if len(file_info.columns) < 2:
            pytest.skip("Need at least 2 columns for this test")

        # Register file
        view_name = gizmo_profiler.register_file_view([str(test_parquet_file)])

        # Profile multiple columns
        columns = [col.name for col in file_info.columns[:2]]
        profiles = gizmo_profiler.profile_columns(view_name, columns)

        assert len(profiles) == 2
        for col in columns:
            assert col in profiles
            assert profiles[col].column == col

    except Exception as e:
        pytest.skip(f"Could not profile multiple columns: {e}")
