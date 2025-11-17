"""Integration tests for Parquet profiling with GizmoSQL.

These tests require a running GizmoSQL instance. They will be skipped if:
- GizmoSQL is not available
- TEST_GIZMOSQL_URI environment variable is not set
"""

import os
from pathlib import Path

import pytest

from table_sleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler

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


@pytest.mark.skipif(not GIZMOSQL_AVAILABLE, reason="TEST_GIZMOSQL_URI not set")
class TestParquetProfilingDockerGizmoSQL:
    """Test Parquet profiling with Docker GizmoSQL instance.

    Requirements: 2.1, 2.2, 2.3, 2.4
    """

    def test_profile_column_with_docker_gizmosql(self):
        """Test profiling a column with Docker GizmoSQL (with Docker paths)."""
        # Skip if Docker paths not configured
        local_data_path = os.getenv("TEST_LOCAL_DATA_PATH")
        docker_data_path = os.getenv("TEST_DOCKER_DATA_PATH")

        if not local_data_path or not docker_data_path:
            pytest.skip("Docker path configuration not available")

        if not TEST_PARQUET_FILE.exists():
            pytest.skip("Test Parquet file not available")

        # Initialize profiler with Docker paths
        profiler = GizmoDuckDbProfiler(
            uri=GIZMOSQL_URI,
            username=os.getenv("TEST_GIZMOSQL_USERNAME", "test_user"),
            password=os.getenv("TEST_GIZMOSQL_PASSWORD", "test_pass"),
            tls_skip_verify=True,
            local_data_path=local_data_path,
            docker_data_path=docker_data_path,
        )

        try:
            # Register file view (path will be converted to Docker path)
            view_name = profiler.register_file_view([str(TEST_PARQUET_FILE)])
            assert view_name is not None

            # Profile a column
            profile = profiler.profile_single_column(view_name, "id")

            # Verify profile results
            assert profile is not None
            assert profile.column == "id"
            assert profile.row_count > 0

        except Exception as e:
            pytest.fail(f"Docker profiling failed: {e}")

    def test_path_outside_docker_mount_fails(self):
        """Test that profiling fails for files outside Docker mount."""
        local_data_path = os.getenv("TEST_LOCAL_DATA_PATH")
        docker_data_path = os.getenv("TEST_DOCKER_DATA_PATH")

        if not local_data_path or not docker_data_path:
            pytest.skip("Docker path configuration not available")

        profiler = GizmoDuckDbProfiler(
            uri=GIZMOSQL_URI,
            username=os.getenv("TEST_GIZMOSQL_USERNAME", "test_user"),
            password=os.getenv("TEST_GIZMOSQL_PASSWORD", "test_pass"),
            tls_skip_verify=True,
            local_data_path=local_data_path,
            docker_data_path=docker_data_path,
        )

        # Try to register a file outside the Docker mount
        outside_file = "/tmp/outside.parquet"

        with pytest.raises(ValueError) as exc_info:
            profiler.register_file_view([outside_file])

        # Verify error message mentions Docker mount
        assert "not within the mounted data directory" in str(exc_info.value)


class TestBackwardCompatibility:
    """Test backward compatibility with existing configurations.

    Requirements: 2.1, 2.2, 2.3, 2.4
    """

    def test_docker_configuration_still_works(self):
        """Test that existing Docker configurations continue to work."""
        # This test verifies the profiler can be initialized with Docker paths
        # (actual connection testing requires running GizmoSQL)

        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="gizmosql_username",
            password="gizmosql_password",
            tls_skip_verify=True,
            local_data_path="data",
            docker_data_path="/data",
        )

        # Verify Docker paths are configured
        assert profiler._local_data_path is not None
        assert profiler._docker_data_path == "/data"

    def test_local_configuration_works(self):
        """Test that new local configurations work."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:10501",
            username="gizmosql_username",
            password="gizmosql_password",
            tls_skip_verify=False,
            # No Docker paths
        )

        # Verify Docker paths are not configured
        assert profiler._local_data_path is None
        assert profiler._docker_data_path is None

    def test_mixed_configuration_scenarios(self):
        """Test various configuration scenarios."""
        # Scenario 1: Only local_data_path set (should disable Docker conversion)
        profiler1 = GizmoDuckDbProfiler(
            uri="grpc://localhost:10501",
            username="test",
            password="test",
            local_data_path="data",
            docker_data_path=None,
        )
        assert profiler1._docker_data_path is None

        # Scenario 2: Only docker_data_path set (should disable Docker conversion)
        profiler2 = GizmoDuckDbProfiler(
            uri="grpc://localhost:10501",
            username="test",
            password="test",
            local_data_path=None,
            docker_data_path="/data",
        )
        assert profiler2._local_data_path is None

        # Scenario 3: Both set (should enable Docker conversion)
        profiler3 = GizmoDuckDbProfiler(
            uri="grpc://localhost:10501",
            username="test",
            password="test",
            local_data_path="data",
            docker_data_path="/data",
        )
        assert profiler3._local_data_path is not None
        assert profiler3._docker_data_path == "/data"


# Instructions for running these tests:
"""
To run these integration tests, you need:

1. A running GizmoSQL instance (local or Docker)
2. Set environment variables:

For local GizmoSQL:
export TEST_GIZMOSQL_URI="grpc://localhost:10501"
export TEST_GIZMOSQL_USERNAME="test_user"
export TEST_GIZMOSQL_PASSWORD="test_pass"

For Docker GizmoSQL:
export TEST_GIZMOSQL_URI="grpc+tls://localhost:31337"
export TEST_GIZMOSQL_USERNAME="gizmosql_username"
export TEST_GIZMOSQL_PASSWORD="gizmosql_password"
export TEST_LOCAL_DATA_PATH="data"
export TEST_DOCKER_DATA_PATH="/data"

3. Create a test Parquet file at tests/data/test.parquet

Then run:
pytest tests/test_parquet_profiling_integration.py -v
"""
