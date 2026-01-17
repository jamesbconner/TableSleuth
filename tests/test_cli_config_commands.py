"""Tests for CLI configuration commands (init and config-check)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from tablesleuth.cli import config_check, init_config


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


class TestInitCommand:
    """Tests for tablesleuth init command."""

    def test_init_help(self, cli_runner: CliRunner) -> None:
        """Test that init command help works."""
        result = cli_runner.invoke(init_config, ["--help"])
        assert result.exit_code == 0
        assert "Initialize TableSleuth configuration files" in result.output
        assert "--force" in result.output

    def test_init_creates_files_in_home(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test init creates config files in home directory."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Mock Path.home() to return our temp directory
            with patch("pathlib.Path.home", return_value=tmp_path):
                # Provide "1" as input for home directory choice
                result = cli_runner.invoke(init_config, input="1\n")

                assert result.exit_code == 0
                assert "Configuration files created successfully!" in result.output

                # Check files were created
                assert (tmp_path / "tablesleuth.toml").exists()
                assert (tmp_path / ".pyiceberg.yaml").exists()

                # Check content
                toml_content = (tmp_path / "tablesleuth.toml").read_text()
                assert "[catalog]" in toml_content
                assert "[gizmosql]" in toml_content

                yaml_content = (tmp_path / ".pyiceberg.yaml").read_text()
                assert "catalog:" in yaml_content

    def test_init_creates_files_in_current_dir(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test init creates config files in current directory."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Provide "2" as input for current directory choice
            result = cli_runner.invoke(init_config, input="2\n")

            assert result.exit_code == 0
            assert "Configuration files created successfully!" in result.output

            # Check files were created in current directory
            assert Path("tablesleuth.toml").exists()
            assert Path(".pyiceberg.yaml").exists()

    def test_init_fails_if_files_exist(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test init fails if config files already exist without --force."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create existing files
            Path("tablesleuth.toml").write_text("existing")

            # Try to init without --force
            result = cli_runner.invoke(init_config, input="2\n")

            assert result.exit_code == 1
            assert "Configuration files already exist" in result.output
            assert "--force" in result.output

    def test_init_force_overwrites_files(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test init with --force overwrites existing files."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create existing files
            Path("tablesleuth.toml").write_text("existing")
            Path(".pyiceberg.yaml").write_text("existing")

            # Init with --force
            result = cli_runner.invoke(init_config, ["--force"], input="2\n")

            assert result.exit_code == 0
            assert "Backed up existing" in result.output
            assert "Configuration files created successfully!" in result.output

            # Check backup files were created
            assert Path("tablesleuth.toml.backup").exists()
            assert Path(".pyiceberg.yaml.backup").exists()

            # Check new files have template content
            toml_content = Path("tablesleuth.toml").read_text()
            assert "[catalog]" in toml_content
            assert "existing" not in toml_content


class TestConfigCheckCommand:
    """Tests for tablesleuth config-check command."""

    def test_config_check_help(self, cli_runner: CliRunner) -> None:
        """Test that config-check command help works."""
        result = cli_runner.invoke(config_check, ["--help"])
        assert result.exit_code == 0
        assert "Check TableSleuth configuration" in result.output
        assert "--verbose" in result.output

    def test_config_check_no_config(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test config-check with no configuration files."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with patch("tablesleuth.config.DEFAULT_CONFIG_PATHS", [tmp_path / "tablesleuth.toml"]):
                result = cli_runner.invoke(config_check)

                assert result.exit_code == 1
                assert "No config file found" in result.output or "⚠" in result.output
                assert "tablesleuth init" in result.output

    def test_config_check_with_valid_config(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test config-check with valid configuration."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create a valid config file
            config_content = """
[catalog]
default = "local"

[gizmosql]
uri = "grpc+tls://localhost:31337"
username = "test_user"
password = "test_pass"
tls_skip_verify = true
"""
            Path("tablesleuth.toml").write_text(config_content)

            with patch("pathlib.Path.cwd", return_value=tmp_path):
                # Mock GizmoSQL connection to avoid actual connection attempt
                with patch("tablesleuth.cli.GizmoDuckDbProfiler") as mock_profiler:
                    mock_profiler.return_value._connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.execute.return_value = None

                    result = cli_runner.invoke(config_check)

                    assert "Config file found" in result.output
                    assert "Config file syntax valid" in result.output

    def test_config_check_verbose(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test config-check with verbose flag."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create a valid config file
            config_content = """
[catalog]
default = "test_catalog"

[gizmosql]
uri = "grpc://localhost:9999"
username = "verbose_user"
password = "verbose_pass"
"""
            Path("tablesleuth.toml").write_text(config_content)

            with patch(
                "tablesleuth.config.DEFAULT_CONFIG_PATHS", [Path.cwd() / "tablesleuth.toml"]
            ):
                with patch("tablesleuth.cli.GizmoDuckDbProfiler"):
                    result = cli_runner.invoke(config_check, ["-v"])

                    assert "Configuration values:" in result.output
                    # Password should be masked
                    assert "verbose_pass" not in result.output or "*" in result.output

    def test_config_check_with_env_vars(
        self, cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config-check shows environment variable overrides."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            Path("tablesleuth.toml").write_text("[catalog]\n[gizmosql]")

            # Set environment variables
            monkeypatch.setenv("TABLESLEUTH_CATALOG_NAME", "env_catalog")
            monkeypatch.setenv("TABLESLEUTH_GIZMO_URI", "grpc://env:1234")

            with patch("pathlib.Path.cwd", return_value=tmp_path):
                with patch("tablesleuth.cli.GizmoDuckDbProfiler"):
                    result = cli_runner.invoke(config_check)

                    assert "Environment Variable Overrides" in result.output
                    assert "TABLESLEUTH_CATALOG_NAME" in result.output
                    assert "TABLESLEUTH_GIZMO_URI" in result.output

    def test_config_check_invalid_toml(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test config-check with invalid TOML syntax."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create invalid TOML
            Path("tablesleuth.toml").write_text("[invalid toml syntax")

            with patch(
                "tablesleuth.config.DEFAULT_CONFIG_PATHS", [Path.cwd() / "tablesleuth.toml"]
            ):
                result = cli_runner.invoke(config_check)

                assert result.exit_code == 1
                # Should show some kind of error
                assert "error" in result.output.lower() or "✗" in result.output

    def test_config_check_pyiceberg_config(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test config-check detects PyIceberg configuration."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            Path("tablesleuth.toml").write_text("[catalog]\n[gizmosql]")

            # Create PyIceberg config
            pyiceberg_content = """
catalog:
  local:
    type: sql
    uri: sqlite:////tmp/catalog.db
  glue:
    type: glue
"""
            Path(".pyiceberg.yaml").write_text(pyiceberg_content)

            with patch(
                "tablesleuth.config.DEFAULT_CONFIG_PATHS", [Path.cwd() / "tablesleuth.toml"]
            ):
                with patch("tablesleuth.cli.GizmoDuckDbProfiler"):
                    result = cli_runner.invoke(config_check, ["-v"])

                    assert "PyIceberg config found" in result.output
                    # Should show catalogs in verbose mode
                    assert "local" in result.output or "glue" in result.output
