"""Integration tests for Parquet profiling with GizmoSQL.

These tests require a running GizmoSQL instance. They will be skipped if:
- GizmoSQL is not available
- TEST_GIZMOSQL_URI environment variable is not set
"""

import os
from pathlib import Path

import pytest

from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler

# Check if GizmoSQL is available for testing
GIZMOSQL_URI = os.getenv("TEST_GIZMOSQL_URI")
GIZMOSQL_AVAILABLE = GIZMOSQL_URI is not None

# Test data paths
TEST_DATA_DIR = Path(__file__).parent / "data"
TEST_PARQUET_FILE = TEST_DATA_DIR / "test.parquet"


@pytest.mark.skipif(not GIZMOSQL_AVAILABLE, reason="TEST_GIZMOSQL_URI not set")
class TestParquetProfilingLocalGizmoSQL:
    """Test Parquet profiling with local GizmoSQL instance.

    Requirements: 1.2, 6.1, 6.2
    """

    def test_profile_column_with_local_gizmosql(self):
        """Test profiling a column with local GizmoSQL (no Docker paths)."""
        # Skip if test file doesn't exist
        if not TEST_PARQUET_FILE.exists():
            pytest.skip("Test Parquet file not available")

        # Initialize profiler without Docker paths
        profiler = GizmoDuckDbProfiler(
            uri=GIZMOSQL_URI,
            username=os.getenv("TEST_GIZMOSQL_USERNAME", "test_user"),
            password=os.getenv("TEST_GIZMOSQL_PASSWORD", "test_pass"),
            tls_skip_verify=False,
            # No Docker paths - local mode
        )

        try:
            # Register file view
            view_name = profiler.register_file_view([str(TEST_PARQUET_FILE)])
            assert view_name is not None

            # Profile a column (assuming the test file has a column named 'id')
            profile = profiler.profile_single_column(view_name, "id")

            # Verify profile results
            assert profile is not None
            assert profile.column == "id"
            assert profile.row_count > 0

        except Exception as e:
            pytest.fail(f"Profiling failed: {e}")

    def test_profile_multiple_columns(self):
        """Test profiling multiple columns with local GizmoSQL."""
        if not TEST_PARQUET_FILE.exists():
            pytest.skip("Test Parquet file not available")

        profiler = GizmoDuckDbProfiler(
            uri=GIZMOSQL_URI,
            username=os.getenv("TEST_GIZMOSQL_USERNAME", "test_user"),
            password=os.getenv("TEST_GIZMOSQL_PASSWORD", "test_pass"),
            tls_skip_verify=False,
        )

        try:
            view_name = profiler.register_file_view([str(TEST_PARQUET_FILE)])

            # Profile multiple columns
            columns = ["id", "name"]  # Adjust based on actual test file schema
            profiles = []

            for column in columns:
                try:
                    profile = profiler.profile_single_column(view_name, column)
                    profiles.append(profile)
                except Exception:
                    # Column might not exist in test file
                    pass

            # Verify we got at least one profile
            assert len(profiles) > 0

        except Exception as e:
            pytest.fail(f"Multi-column profiling failed: {e}")

    def test_connection_error_handling(self):
        """Test error handling when GizmoSQL is not available."""
        # Use invalid URI to trigger connection error
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:99999",  # Invalid port
            username="test_user",
            password="test_pass",
            tls_skip_verify=False,
        )

        # Attempt to register file view should fail with connection-related error
        with pytest.raises((ConnectionError, OSError, RuntimeError)):
            profiler.register_file_view([str(TEST_PARQUET_FILE)])


# Instructions for running these tests:
"""
To run these integration tests, you need:

1. A running GizmoSQL instance
2. Set environment variables:

export TEST_GIZMOSQL_URI="grpc+tls://localhost:31337"
export TEST_GIZMOSQL_USERNAME="test_user"
export TEST_GIZMOSQL_PASSWORD="test_pass"

3. Create a test Parquet file at tests/data/test.parquet

Then run:
pytest tests/test_parquet_profiling_integration.py -v
"""
