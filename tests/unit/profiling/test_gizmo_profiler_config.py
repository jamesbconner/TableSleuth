"""Tests for GizmoDuckDbProfiler configuration handling."""

from pathlib import Path
from unittest.mock import patch

import pytest

from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler, _clean_file_path


class TestGizmoProfilerConfiguration:
    """Test configuration handling in GizmoDuckDbProfiler."""

    def test_profiler_initialization(self):
        """Test basic profiler initialization."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
            tls_skip_verify=True,
        )

        assert profiler._uri == "grpc+tls://localhost:31337"
        assert profiler._username == "test_user"
        assert profiler._password == "test_pass"
        assert profiler._tls_skip_verify is True

    def test_clean_file_path_removes_prefix(self):
        """Test that file:// prefix is removed from paths."""
        # Test with file:// prefix
        assert _clean_file_path("file:///path/to/file.parquet") == "/path/to/file.parquet"

        # Test without prefix
        assert _clean_file_path("/path/to/file.parquet") == "/path/to/file.parquet"

        # Test with relative path
        assert _clean_file_path("data/file.parquet") == "data/file.parquet"

    def test_register_file_view_cleans_paths(self):
        """Test that register_file_view cleans file:// prefixes from paths."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        # Register files with file:// prefix
        file_paths = [
            "file:///path/to/file1.parquet",
            "file:///path/to/file2.parquet",
        ]

        view_name = profiler.register_file_view(file_paths, "test_view")

        # Verify paths were cleaned and stored
        assert view_name == "test_view"
        assert hasattr(profiler, "_view_paths")
        assert "test_view" in profiler._view_paths

        stored_paths = profiler._view_paths["test_view"]
        # All stored paths should have file:// prefix removed
        for path in stored_paths:
            assert not path.startswith("file://")
            assert path.startswith("/path/to/")

    def test_register_file_view_without_prefix(self):
        """Test that register_file_view handles paths without file:// prefix."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        # Register files with absolute paths
        file_paths = [
            "/absolute/path/to/file1.parquet",
            "/absolute/path/to/file2.parquet",
        ]

        view_name = profiler.register_file_view(file_paths, "test_view")

        # Verify paths were stored as-is
        assert view_name == "test_view"
        stored_paths = profiler._view_paths["test_view"]
        assert stored_paths == file_paths

    def test_register_file_view_auto_generates_name(self):
        """Test that register_file_view auto-generates view name when not provided."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        file_paths = ["/path/to/file.parquet"]
        view_name = profiler.register_file_view(file_paths)

        # Verify auto-generated name
        assert view_name.startswith("files_")
        assert len(view_name) > 6  # "files_" + hash

    def test_register_file_view_empty_paths_raises(self):
        """Test that register_file_view raises ValueError for empty paths."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        with pytest.raises(ValueError, match="file_paths cannot be empty"):
            profiler.register_file_view([])

    def test_clear_views(self):
        """Test that clear_views removes all registered views."""
        profiler = GizmoDuckDbProfiler(
            uri="grpc+tls://localhost:31337",
            username="test_user",
            password="test_pass",
        )

        # Register some views
        profiler.register_file_view(["/path/to/file1.parquet"], "view1")
        profiler.register_file_view(["/path/to/file2.parquet"], "view2")

        assert len(profiler._view_paths) == 2

        # Clear views
        profiler.clear_views()

        assert len(profiler._view_paths) == 0


class TestConfigurationLoading:
    """Test configuration loading from environment and TOML."""

    def test_config_loads_basic_settings(self, monkeypatch):
        """Test that configuration loads basic GizmoSQL settings."""
        from tablesleuth.config import load_config

        # Set environment variables
        monkeypatch.setenv("TABLESLEUTH_GIZMO_URI", "grpc://custom:9999")
        monkeypatch.setenv("TABLESLEUTH_GIZMO_USERNAME", "custom_user")
        monkeypatch.setenv("TABLESLEUTH_GIZMO_PASSWORD", "custom_pass")

        config = load_config()

        # Verify environment variables are loaded
        assert config.gizmosql.uri == "grpc://custom:9999"
        assert config.gizmosql.username == "custom_user"
        assert config.gizmosql.password == "custom_pass"

    def test_config_uses_defaults_when_not_set(self, monkeypatch):
        """Test that configuration uses defaults when not configured."""
        from tablesleuth.config import load_config

        # Clear any environment variables
        monkeypatch.delenv("TABLESLEUTH_GIZMO_URI", raising=False)
        monkeypatch.delenv("TABLESLEUTH_GIZMO_USERNAME", raising=False)
        monkeypatch.delenv("TABLESLEUTH_GIZMO_PASSWORD", raising=False)

        config = load_config()

        # Verify config is loaded (values may come from TOML or defaults)
        assert config.gizmosql.uri is not None
        assert config.gizmosql.username is not None
        assert config.gizmosql.password is not None
        assert isinstance(config.gizmosql.tls_skip_verify, bool)
