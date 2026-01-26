"""Tests for CLI configuration commands (init and config-check)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from tablesleuth.cli.config_check import config_check
from tablesleuth.cli.init import init as init_config


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
        """Test init with --force overwrites existing files without backup."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Create existing files
            Path("tablesleuth.toml").write_text("existing")
            Path(".pyiceberg.yaml").write_text("existing")

            # Init with --force
            result = cli_runner.invoke(init_config, ["--force"], input="2\n")

            assert result.exit_code == 0
            assert "Configuration files created successfully!" in result.output
            # Should not mention backups
            assert "Backed up" not in result.output
            assert "backup" not in result.output.lower()

            # Check backup files were NOT created
            assert not Path("tablesleuth.toml.backup").exists()
            assert not Path(".pyiceberg.yaml.backup").exists()

            # Check new files have template content (not "existing")
            toml_content = Path("tablesleuth.toml").read_text()
            assert "[catalog]" in toml_content
            assert "existing" not in toml_content

    def test_init_force_can_run_multiple_times(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test init with --force can be run multiple times (Windows compatibility)."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # First init
            result1 = cli_runner.invoke(init_config, ["--force"], input="2\n")
            assert result1.exit_code == 0

            # Modify files
            Path("tablesleuth.toml").write_text("modified")

            # Second init with --force should succeed (no backup file collision)
            result2 = cli_runner.invoke(init_config, ["--force"], input="2\n")
            assert result2.exit_code == 0

            # Files should have template content again
            toml_content = Path("tablesleuth.toml").read_text()
            assert "[catalog]" in toml_content
            assert "modified" not in toml_content


class TestConfigCheckCommand:
    """Tests for tablesleuth config-check command."""

    def test_config_check_help(self, cli_runner: CliRunner) -> None:
        """Test that config-check command help works."""
        result = cli_runner.invoke(config_check, ["--help"])
        assert result.exit_code == 0
        assert "Check TableSleuth configuration" in result.output
        assert "--verbose" in result.output
        assert "--with-gizmosql" in result.output

    def test_config_check_no_config(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test config-check with no configuration files."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            with patch("tablesleuth.config.DEFAULT_CONFIG_PATHS", [tmp_path / "tablesleuth.toml"]):
                result = cli_runner.invoke(config_check)

                # Should warn but not fail (GizmoSQL is optional and skipped by default)
                assert "No config file found" in result.output or "⚠" in result.output
                assert "tablesleuth init" in result.output
                # GizmoSQL should be skipped
                assert "Skipped" in result.output or "⊘" in result.output

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
                result = cli_runner.invoke(config_check)

                assert "Config file found" in result.output
                assert "Config file syntax valid" in result.output
                # GizmoSQL should be skipped by default
                assert "Skipped" in result.output or "⊘" in result.output

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
                result = cli_runner.invoke(config_check, ["-v"])

                assert "PyIceberg config found" in result.output
                # Should show catalogs in verbose mode
                assert "local" in result.output or "glue" in result.output

    def test_config_check_invalid_env_var(
        self, cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config-check handles invalid TABLESLEUTH_CONFIG gracefully."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Set TABLESLEUTH_CONFIG to non-existent file
            monkeypatch.setenv("TABLESLEUTH_CONFIG", "/nonexistent/config.toml")

            result = cli_runner.invoke(config_check)

            assert result.exit_code == 1
            assert "TABLESLEUTH_CONFIG" in result.output
            assert "non-existent" in result.output or "not found" in result.output.lower()

    def test_config_check_invalid_env_var_verbose(
        self, cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config-check handles invalid TABLESLEUTH_CONFIG with verbose flag."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Set TABLESLEUTH_CONFIG to non-existent file
            monkeypatch.setenv("TABLESLEUTH_CONFIG", "/nonexistent/config.toml")

            result = cli_runner.invoke(config_check, ["-v"])

            assert result.exit_code == 1
            assert "TABLESLEUTH_CONFIG" in result.output
            # Should not crash with unhandled exception
            assert "Traceback" not in result.output

    def test_config_check_invalid_env_var_no_misleading_message(
        self, cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test config-check doesn't show misleading 'No config file found' after error."""
        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Set TABLESLEUTH_CONFIG to non-existent file
            monkeypatch.setenv("TABLESLEUTH_CONFIG", "/nonexistent/config.toml")

            result = cli_runner.invoke(config_check)

            assert result.exit_code == 1
            # Should show the error about TABLESLEUTH_CONFIG
            assert "TABLESLEUTH_CONFIG" in result.output
            assert "non-existent" in result.output or "not found" in result.output.lower()
            # Should NOT show the misleading "No config file found (using defaults)" message
            assert "No config file found (using defaults)" not in result.output
            assert "using defaults" not in result.output.lower()


class TestCLIConfigErrorHandling:
    """Tests for configuration error handling in main CLI commands."""

    def test_parquet_invalid_env_var(
        self, cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test parquet command handles invalid TABLESLEUTH_CONFIG gracefully."""
        from tablesleuth.cli.parquet import parquet

        # Set TABLESLEUTH_CONFIG to non-existent file
        monkeypatch.setenv("TABLESLEUTH_CONFIG", "/nonexistent/config.toml")

        result = cli_runner.invoke(parquet, ["test.parquet"])

        assert result.exit_code == 1
        assert "TABLESLEUTH_CONFIG" in result.output
        assert "tablesleuth init" in result.output
        # Should not show traceback
        assert "Traceback" not in result.output

    def test_iceberg_invalid_env_var(
        self, cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test iceberg command handles invalid TABLESLEUTH_CONFIG gracefully."""
        from tablesleuth.cli.iceberg import iceberg as iceberg_viewer

        # Set TABLESLEUTH_CONFIG to non-existent file
        monkeypatch.setenv("TABLESLEUTH_CONFIG", "/nonexistent/config.toml")

        result = cli_runner.invoke(iceberg_viewer, ["--catalog", "test", "--table", "db.table"])

        assert result.exit_code == 1
        assert "TABLESLEUTH_CONFIG" in result.output
        assert "tablesleuth init" in result.output
        # Should not show traceback
        assert "Traceback" not in result.output

    def test_generated_config_is_valid_toml(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that generated config file is valid TOML (no null values)."""
        import tomllib

        from tablesleuth.utils.config_templates import get_tablesleuth_template

        # Get the template
        template = get_tablesleuth_template()

        # Try to parse it as TOML
        try:
            config = tomllib.loads(template)
            # Should parse successfully
            assert "catalog" in config
            assert "gizmosql" in config
        except Exception as e:
            pytest.fail(f"Generated config template is invalid TOML: {e}")

    def test_init_creates_valid_toml(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test that init command creates a valid TOML file."""
        import tomllib

        with cli_runner.isolated_filesystem(temp_dir=tmp_path):
            # Run init
            result = cli_runner.invoke(init_config, input="2\n")

            assert result.exit_code == 0
            assert Path("tablesleuth.toml").exists()

            # Try to parse the generated file
            try:
                with open("tablesleuth.toml", "rb") as f:
                    config = tomllib.load(f)
                # Should parse successfully
                assert "catalog" in config
                assert "gizmosql" in config
            except Exception as e:
                pytest.fail(f"Generated config file is invalid TOML: {e}")

    def test_config_check_with_gizmosql_flag(self, cli_runner: CliRunner, tmp_path: Path) -> None:
        """Test config-check with --with-gizmosql flag tests GizmoSQL connection."""
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
                # Mock GizmoSQL connection to succeed
                with patch("tablesleuth.cli.config_check.GizmoDuckDbProfiler") as mock_profiler:
                    mock_cursor = Mock()
                    mock_cursor.execute.return_value = None
                    mock_cursor.fetchone.return_value = (1,)

                    mock_conn = Mock()
                    mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
                    mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)

                    mock_profiler.return_value._connect.return_value.__enter__ = Mock(
                        return_value=mock_conn
                    )
                    mock_profiler.return_value._connect.return_value.__exit__ = Mock(
                        return_value=False
                    )

                    result = cli_runner.invoke(config_check, ["--with-gizmosql"])

                    assert "GizmoSQL connection successful" in result.output
                    assert result.exit_code == 0

    def test_config_check_with_gizmosql_flag_failure(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test config-check with --with-gizmosql flag handles connection failure."""
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
                # Mock GizmoSQL connection to fail
                with patch("tablesleuth.cli.config_check.GizmoDuckDbProfiler") as mock_profiler:
                    mock_profiler.return_value._connect.side_effect = Exception(
                        "Connection refused"
                    )

                    result = cli_runner.invoke(config_check, ["--with-gizmosql"])

                    assert "GizmoSQL connection failed" in result.output
                    assert "Connection refused" in result.output
                    assert result.exit_code == 1

    def test_config_check_without_gizmosql_flag_skips_test(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """Test config-check without --with-gizmosql flag skips GizmoSQL test."""
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
                result = cli_runner.invoke(config_check)

                # Should skip GizmoSQL test
                assert "Skipped" in result.output or "⊘" in result.output
                assert "--with-gizmosql" in result.output
                # Should not attempt connection
                assert "connection successful" not in result.output.lower()
                assert "connection failed" not in result.output.lower()
