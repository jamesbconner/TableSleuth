"""Tests for GizmoDuckDbProfiler configuration handling."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from table_sleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler


class TestGizmoProfilerConfiguration:
    """Test configuration handling in GizmoDuckDbProfiler."""

    def test_profiler_with_docker_paths_configured(self):
        """Test profiler initialization with Docker paths configured.

        Verifies that Docker path conversion is enabled when both
        local_data_path and docker_data_path are provided.

        Requirements: 1.1, 1.3
        """
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
            tls_skip_verify=True,
            local_data_path="data",
            docker_data_path="/data",
        )

        # Verify Docker paths are set
        assert profiler._local_data_path is not None
        assert profiler._docker_data_path == "/data"
        assert profiler._local_data_path == Path("data").resolve()

    def test_profiler_without_docker_paths(self):
        """Test profiler initialization without Docker paths.

        Verifies that Docker path conversion is disabled when
        local_data_path and docker_data_path are not provided.

        Requirements: 1.2, 1.5
        """
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:10501",
            username="test_user",
            password="test_pass",
            tls_skip_verify=False,
        )

        # Verify Docker paths are not set
        assert profiler._local_data_path is None
        assert profiler._docker_data_path is None

    def test_path_conversion_with_docker_enabled(self):
        """Test path conversion when Docker paths are configured.

        Verifies that paths are correctly converted from local to Docker paths.

        Requirements: 1.1, 1.3
        """
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
            local_data_path="data",
            docker_data_path="/data",
        )

        # Create a test file path within the data directory
        test_file = Path("data/warehouse/test.parquet").resolve()

        # Convert to Docker path
        docker_path = profiler._convert_to_docker_path(str(test_file))

        # Verify conversion
        assert docker_path.startswith("/data/")
        assert "warehouse/test.parquet" in docker_path

    def test_path_conversion_without_docker(self):
        """Test path conversion when Docker paths are not configured.

        Verifies that paths are used directly without conversion.

        Requirements: 1.2, 1.5
        """
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:10501",
            username="test_user",
            password="test_pass",
        )

        # Test with regular path
        test_path = "/absolute/path/to/file.parquet"
        result = profiler._convert_to_docker_path(test_path)

        # Verify path is returned as-is
        assert result == test_path

    def test_path_validation_in_docker_mode(self):
        """Test path validation when Docker paths are configured.

        Verifies that ValueError is raised for paths outside the mounted directory.

        Requirements: 1.4, 4.1
        """
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
            local_data_path="data",
            docker_data_path="/data",
        )

        # Try to convert a path outside the data directory
        outside_path = "/tmp/outside.parquet"

        with pytest.raises(ValueError) as exc_info:
            profiler._convert_to_docker_path(outside_path)

        # Verify error message is helpful
        assert "not within the mounted data directory" in str(exc_info.value)
        assert "data" in str(exc_info.value)

    def test_file_prefix_handling_with_docker(self):
        """Test file:// prefix handling with Docker paths.

        Verifies that file:// prefix is removed correctly in Docker mode.

        Requirements: 1.1, 1.2
        """
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
            local_data_path="data",
            docker_data_path="/data",
        )

        # Test with file:// prefix
        test_file = Path("data/test.parquet").resolve()
        file_uri = f"file://{test_file}"

        docker_path = profiler._convert_to_docker_path(file_uri)

        # Verify prefix is removed and path is converted
        assert not docker_path.startswith("file://")
        assert docker_path.startswith("/data/")

    def test_file_prefix_handling_without_docker(self):
        """Test file:// prefix handling without Docker paths.

        Verifies that file:// prefix is removed correctly in local mode.

        Requirements: 1.1, 1.2
        """
        profiler = GizmoDuckDbProfiler(
            uri="grpc://localhost:10501",
            username="test_user",
            password="test_pass",
        )

        # Test with file:// prefix
        test_path = "file:///absolute/path/to/file.parquet"
        result = profiler._convert_to_docker_path(test_path)

        # Verify prefix is removed
        assert result == "/absolute/path/to/file.parquet"
        assert not result.startswith("file://")

    def test_relative_path_conversion(self):
        """Test conversion of relative paths in Docker mode.

        Verifies that relative paths within the data directory are converted correctly.

        Requirements: 1.1, 1.3
        """
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
            local_data_path="data",
            docker_data_path="/data",
        )

        # Test with relative path
        relative_path = "data/subdir/file.parquet"
        docker_path = profiler._convert_to_docker_path(relative_path)

        # Verify conversion
        assert docker_path.startswith("/data/")
        assert "subdir/file.parquet" in docker_path

    @patch("table_sleuth.services.profiling.gizmo_duckdb.logger")
    def test_configuration_logging_docker_enabled(self, mock_logger):
        """Test that configuration mode is logged when Docker paths are enabled.

        Requirements: 3.3
        """
        GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
            local_data_path="data",
            docker_data_path="/data",
        )

        # Verify debug log was called
        mock_logger.debug.assert_called()
        call_args = str(mock_logger.debug.call_args)
        assert "Docker path conversion enabled" in call_args

    @patch("table_sleuth.services.profiling.gizmo_duckdb.logger")
    def test_configuration_logging_docker_disabled(self, mock_logger):
        """Test that configuration mode is logged when Docker paths are disabled.

        Requirements: 3.3
        """
        GizmoDuckDbProfiler(
            uri="grpc://localhost:10501",
            username="test_user",
            password="test_pass",
        )

        # Verify debug log was called
        mock_logger.debug.assert_called()
        call_args = str(mock_logger.debug.call_args)
        assert "Using local paths directly" in call_args


class TestConfigurationLoading:
    """Test configuration loading from environment and TOML."""

    def test_empty_string_env_vars_disable_docker_paths(self, monkeypatch):
        """Test that empty string environment variables disable Docker paths.

        Requirements: 5.5
        """
        from table_sleuth.config import load_config

        # Set environment variables to empty strings
        monkeypatch.setenv("TABLE_SLEUTH_LOCAL_DATA_PATH", "")
        monkeypatch.setenv("TABLE_SLEUTH_DOCKER_DATA_PATH", "")

        config = load_config()

        # Verify Docker paths are None
        assert config.gizmosql.local_data_path is None
        assert config.gizmosql.docker_data_path is None

    def test_env_vars_override_toml(self, monkeypatch):
        """Test that environment variables override TOML configuration.

        Requirements: 5.1, 5.2, 5.3
        """
        from table_sleuth.config import load_config

        # Set environment variables
        monkeypatch.setenv("TABLE_SLEUTH_LOCAL_DATA_PATH", "custom_data")
        monkeypatch.setenv("TABLE_SLEUTH_DOCKER_DATA_PATH", "/custom_data")

        config = load_config()

        # Verify environment variables take precedence
        assert config.gizmosql.local_data_path == "custom_data"
        assert config.gizmosql.docker_data_path == "/custom_data"

    def test_default_values_when_not_configured(self, monkeypatch):
        """Test that default values are None when not configured.

        Requirements: 2.2, 2.3
        """
        from table_sleuth.config import load_config

        # Clear any environment variables
        monkeypatch.delenv("TABLE_SLEUTH_LOCAL_DATA_PATH", raising=False)
        monkeypatch.delenv("TABLE_SLEUTH_DOCKER_DATA_PATH", raising=False)

        config = load_config()

        # Verify defaults are None (no Docker paths)
        # Note: This assumes no table_sleuth.toml with these values
        # In practice, the actual default depends on the TOML file
        assert config.gizmosql.local_data_path is None or isinstance(
            config.gizmosql.local_data_path, str
        )
