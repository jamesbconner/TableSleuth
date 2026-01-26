"""Tests for CLI functionality."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tablesleuth.cli import main
from tablesleuth.cli.config_check import config_check
from tablesleuth.cli.delta import delta
from tablesleuth.cli.helpers import (
    is_catalog_error as _is_catalog_error,
)
from tablesleuth.cli.helpers import (
    is_gizmosql_error as _is_gizmosql_error,
)
from tablesleuth.cli.helpers import (
    suggest_init_on_config_error as _suggest_init_on_config_error,
)
from tablesleuth.cli.iceberg import iceberg as iceberg_viewer
from tablesleuth.cli.init import init as init_config
from tablesleuth.cli.parquet import parquet


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for config files."""
    return tmp_path


# ============================================================================
# Main Command Tests
# ============================================================================


def test_main_command_exists(cli_runner: CliRunner) -> None:
    """Test that main command exists."""
    result = cli_runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "TableSleuth" in result.output


def test_version_flag(cli_runner: CliRunner) -> None:
    """Test version flag."""
    result = cli_runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower() or "tablesleuth" in result.output.lower()


def test_main_help_shows_commands(cli_runner: CliRunner) -> None:
    """Test that main help shows available commands."""
    result = cli_runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "parquet" in result.output.lower()
    assert "iceberg" in result.output.lower()
    assert "delta" in result.output.lower()
    assert "init" in result.output.lower()
    assert "config-check" in result.output.lower()


# ============================================================================
# Helper Function Tests
# ============================================================================


def test_suggest_init_on_config_error() -> None:
    """Test _suggest_init_on_config_error helper function."""
    error_msg = "Configuration error occurred"
    result = _suggest_init_on_config_error(error_msg)

    assert "Configuration error occurred" in result
    assert "Configuration may be missing or incomplete" in result
    assert "tablesleuth init" in result
    assert "edit them to match your environment" in result


def test_is_catalog_error_with_catalog_keyword() -> None:
    """Test _is_catalog_error detects catalog-related errors."""
    assert _is_catalog_error(Exception("catalog not found"))
    assert _is_catalog_error(Exception("no such catalog"))
    assert _is_catalog_error(Exception("pyiceberg error"))
    assert _is_catalog_error(Exception("warehouse missing"))
    assert _is_catalog_error(Exception("metadata error"))


def test_is_catalog_error_with_non_catalog_error() -> None:
    """Test _is_catalog_error returns False for non-catalog errors."""
    assert not _is_catalog_error(Exception("file not found"))
    assert not _is_catalog_error(Exception("connection timeout"))
    assert not _is_catalog_error(Exception("invalid argument"))


def test_is_gizmosql_error_with_gizmosql_keyword() -> None:
    """Test _is_gizmosql_error detects GizmoSQL-related errors."""
    assert _is_gizmosql_error(Exception("flightsql connection failed"))
    assert _is_gizmosql_error(Exception("grpc error"))
    assert _is_gizmosql_error(Exception("connection refused"))
    assert _is_gizmosql_error(Exception("connection error"))
    assert _is_gizmosql_error(Exception("dial tcp failed"))
    assert _is_gizmosql_error(Exception("gizmosql unavailable"))


def test_is_gizmosql_error_with_non_gizmosql_error() -> None:
    """Test _is_gizmosql_error returns False for non-GizmoSQL errors."""
    assert not _is_gizmosql_error(Exception("file not found"))
    assert not _is_gizmosql_error(Exception("catalog error"))
    assert not _is_gizmosql_error(Exception("invalid table"))


# ============================================================================
# Parquet Command Tests
# ============================================================================


def test_parquet_command_exists(cli_runner: CliRunner) -> None:
    """Test that parquet command exists."""
    result = cli_runner.invoke(main, ["parquet", "--help"])
    assert result.exit_code == 0
    assert "parquet" in result.output.lower()


def test_parquet_help_shows_examples(cli_runner: CliRunner) -> None:
    """Test that parquet help shows examples."""
    result = cli_runner.invoke(main, ["parquet", "--help"])
    assert result.exit_code == 0
    assert "Examples" in result.output or "examples" in result.output


def test_parquet_nonexistent_file(cli_runner: CliRunner) -> None:
    """Test parquet with nonexistent file."""
    result = cli_runner.invoke(parquet, ["nonexistent.parquet"])
    assert result.exit_code != 0
    assert "does not exist" in result.output.lower() or "error" in result.output.lower()


def test_parquet_with_verbose_flag(cli_runner: CliRunner) -> None:
    """Test parquet with verbose flag."""
    result = cli_runner.invoke(parquet, ["--verbose", "nonexistent.parquet"])
    assert result.exit_code != 0


def test_parquet_directory_nonexistent(cli_runner: CliRunner) -> None:
    """Test parquet with nonexistent directory."""
    result = cli_runner.invoke(parquet, ["/nonexistent/directory"])
    assert result.exit_code != 0
    assert "error" in result.output.lower()


def test_parquet_command_parameters(cli_runner: CliRunner) -> None:
    """Test that parquet command has required parameters."""
    result = cli_runner.invoke(main, ["parquet", "--help"])
    assert result.exit_code == 0

    # Check for required parameters
    assert "PATH" in result.output or "path" in result.output
    assert "--catalog" in result.output
    assert "--verbose" in result.output
    assert "--region" in result.output


def test_parquet_with_catalog_option(cli_runner: CliRunner) -> None:
    """Test parquet command with catalog option."""
    result = cli_runner.invoke(parquet, ["--catalog", "test_catalog", "test.table"])
    assert result.exit_code != 0  # Will fail without proper setup, but tests option parsing


def test_parquet_with_region_option(cli_runner: CliRunner) -> None:
    """Test parquet command with region option."""
    result = cli_runner.invoke(parquet, ["--region", "us-west-2", "nonexistent.parquet"])
    assert result.exit_code != 0  # Will fail, but tests option parsing


# ============================================================================
# Iceberg Command Tests
# ============================================================================


def test_iceberg_command_exists(cli_runner: CliRunner) -> None:
    """Test that iceberg command exists."""
    result = cli_runner.invoke(main, ["iceberg", "--help"])
    assert result.exit_code == 0
    assert "iceberg" in result.output.lower()


def test_iceberg_help_shows_examples(cli_runner: CliRunner) -> None:
    """Test that iceberg help shows examples."""
    result = cli_runner.invoke(main, ["iceberg", "--help"])
    assert result.exit_code == 0
    assert "Examples" in result.output or "examples" in result.output


def test_iceberg_without_args(cli_runner: CliRunner) -> None:
    """Test iceberg command without required arguments."""
    result = cli_runner.invoke(iceberg_viewer, [])
    assert result.exit_code != 0
    assert "error" in result.output.lower() or "must provide" in result.output.lower()


def test_iceberg_with_catalog_but_no_table(cli_runner: CliRunner) -> None:
    """Test iceberg command with catalog but no table."""
    result = cli_runner.invoke(iceberg_viewer, ["--catalog", "test_catalog"])
    assert result.exit_code != 0


def test_iceberg_with_verbose_flag(cli_runner: CliRunner) -> None:
    """Test iceberg command with verbose flag."""
    result = cli_runner.invoke(
        iceberg_viewer, ["--verbose", "--catalog", "test", "--table", "test.table"]
    )
    assert result.exit_code != 0  # Will fail without proper setup


def test_iceberg_command_parameters(cli_runner: CliRunner) -> None:
    """Test that iceberg command has required parameters."""
    result = cli_runner.invoke(main, ["iceberg", "--help"])
    assert result.exit_code == 0

    assert "--catalog" in result.output
    assert "--table" in result.output
    assert "--verbose" in result.output


# ============================================================================
# Delta Command Tests
# ============================================================================


def test_delta_command_exists(cli_runner: CliRunner) -> None:
    """Test that delta command exists."""
    result = cli_runner.invoke(main, ["delta", "--help"])
    assert result.exit_code == 0
    assert "delta" in result.output.lower()


def test_delta_help_shows_examples(cli_runner: CliRunner) -> None:
    """Test that delta help shows examples."""
    result = cli_runner.invoke(main, ["delta", "--help"])
    assert result.exit_code == 0
    assert "Examples" in result.output or "examples" in result.output


def test_delta_nonexistent_path(cli_runner: CliRunner) -> None:
    """Test delta with nonexistent path."""
    result = cli_runner.invoke(delta, ["/nonexistent/delta/table"])
    assert result.exit_code != 0
    assert "error" in result.output.lower() or "failed" in result.output.lower()


def test_delta_with_version_option(cli_runner: CliRunner) -> None:
    """Test delta command with version option."""
    result = cli_runner.invoke(delta, ["--version", "42", "/nonexistent/table"])
    assert result.exit_code != 0  # Will fail, but tests option parsing


def test_delta_with_storage_option(cli_runner: CliRunner) -> None:
    """Test delta command with storage option."""
    result = cli_runner.invoke(
        delta, ["--storage-option", "AWS_REGION=us-west-2", "/nonexistent/table"]
    )
    assert result.exit_code != 0  # Will fail, but tests option parsing


def test_delta_with_invalid_storage_option_format(cli_runner: CliRunner) -> None:
    """Test delta command with invalid storage option format."""
    result = cli_runner.invoke(delta, ["--storage-option", "INVALID_FORMAT", "/nonexistent/table"])
    assert result.exit_code != 0
    assert "invalid storage option format" in result.output.lower()


def test_delta_with_verbose_flag(cli_runner: CliRunner) -> None:
    """Test delta command with verbose flag."""
    result = cli_runner.invoke(delta, ["--verbose", "/nonexistent/table"])
    assert result.exit_code != 0  # Will fail, but tests option parsing


def test_delta_command_parameters(cli_runner: CliRunner) -> None:
    """Test that delta command has required parameters."""
    result = cli_runner.invoke(main, ["delta", "--help"])
    assert result.exit_code == 0

    assert "PATH" in result.output or "path" in result.output
    assert "--version" in result.output
    assert "--storage-option" in result.output
    assert "--verbose" in result.output


def test_delta_with_multiple_storage_options(cli_runner: CliRunner) -> None:
    """Test delta command with multiple storage options."""
    result = cli_runner.invoke(
        delta,
        [
            "--storage-option",
            "AWS_REGION=us-west-2",
            "--storage-option",
            "AWS_PROFILE=my-profile",
            "/nonexistent/table",
        ],
    )
    assert result.exit_code != 0  # Will fail, but tests option parsing


# ============================================================================
# Init Command Tests
# ============================================================================


def test_init_command_exists(cli_runner: CliRunner) -> None:
    """Test that init command exists."""
    result = cli_runner.invoke(main, ["init", "--help"])
    assert result.exit_code == 0
    assert "init" in result.output.lower()


def test_init_help_shows_examples(cli_runner: CliRunner) -> None:
    """Test that init help shows examples."""
    result = cli_runner.invoke(main, ["init", "--help"])
    assert result.exit_code == 0
    assert "Examples" in result.output or "examples" in result.output


def test_init_creates_config_files_in_home(
    cli_runner: CliRunner, temp_config_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test init command creates config files in home directory."""
    with cli_runner.isolated_filesystem():
        # Mock Path.home() to return current directory
        monkeypatch.setattr(Path, "home", lambda: Path.cwd())

        # Simulate user choosing home directory (option 1)
        result = cli_runner.invoke(init_config, input="1\n")

        # Check that command ran successfully
        assert result.exit_code == 0
        assert "Configuration files created successfully" in result.output


def test_init_creates_config_files_in_current_dir(
    cli_runner: CliRunner, temp_config_dir: Path
) -> None:
    """Test init command creates config files in current directory."""
    with cli_runner.isolated_filesystem():
        # Simulate user choosing current directory (option 2)
        result = cli_runner.invoke(init_config, input="2\n")

        # Check that command ran successfully
        assert result.exit_code == 0
        assert "Configuration files created successfully" in result.output


def test_init_with_force_flag(cli_runner: CliRunner, temp_config_dir: Path) -> None:
    """Test init command with force flag overwrites existing files."""
    with cli_runner.isolated_filesystem():
        # Create initial config files
        result1 = cli_runner.invoke(init_config, input="2\n")
        assert result1.exit_code == 0

        # Try to create again with force flag
        result2 = cli_runner.invoke(init_config, ["--force"], input="2\n")
        assert result2.exit_code == 0
        assert "Configuration files created successfully" in result2.output


def test_init_without_force_fails_on_existing_files(
    cli_runner: CliRunner, temp_config_dir: Path
) -> None:
    """Test init command fails when files exist without force flag."""
    with cli_runner.isolated_filesystem():
        # Create initial config files
        result1 = cli_runner.invoke(init_config, input="2\n")
        assert result1.exit_code == 0

        # Try to create again without force flag
        result2 = cli_runner.invoke(init_config, input="2\n")
        assert result2.exit_code != 0
        assert "already exist" in result2.output.lower()


def test_init_command_parameters(cli_runner: CliRunner) -> None:
    """Test that init command has required parameters."""
    result = cli_runner.invoke(main, ["init", "--help"])
    assert result.exit_code == 0

    assert "--force" in result.output


# ============================================================================
# Config-Check Command Tests
# ============================================================================


def test_config_check_command_exists(cli_runner: CliRunner) -> None:
    """Test that config-check command exists."""
    result = cli_runner.invoke(main, ["config-check", "--help"])
    assert result.exit_code == 0
    assert "config-check" in result.output.lower()


def test_config_check_help_shows_examples(cli_runner: CliRunner) -> None:
    """Test that config-check help shows examples."""
    result = cli_runner.invoke(main, ["config-check", "--help"])
    assert result.exit_code == 0
    assert "Examples" in result.output or "examples" in result.output


def test_config_check_basic(cli_runner: CliRunner) -> None:
    """Test basic config-check command."""
    result = cli_runner.invoke(config_check, [])

    # Should run without crashing
    assert "TableSleuth Configuration Check" in result.output
    assert "TableSleuth Configuration" in result.output
    assert "PyIceberg Configuration" in result.output


def test_config_check_with_verbose_flag(cli_runner: CliRunner) -> None:
    """Test config-check command with verbose flag."""
    result = cli_runner.invoke(config_check, ["--verbose"])

    assert "TableSleuth Configuration Check" in result.output


def test_config_check_with_gizmosql_flag(cli_runner: CliRunner) -> None:
    """Test config-check command with gizmosql flag."""
    result = cli_runner.invoke(config_check, ["--with-gizmosql"])

    assert "TableSleuth Configuration Check" in result.output
    assert "GizmoSQL Connection Test" in result.output


def test_config_check_command_parameters(cli_runner: CliRunner) -> None:
    """Test that config-check command has required parameters."""
    result = cli_runner.invoke(main, ["config-check", "--help"])
    assert result.exit_code == 0

    assert "--verbose" in result.output
    assert "--with-gizmosql" in result.output


def test_config_check_shows_environment_variables(cli_runner: CliRunner) -> None:
    """Test config-check shows environment variable section."""
    result = cli_runner.invoke(config_check, [])

    assert "Environment Variable Overrides" in result.output


def test_config_check_with_env_var_set(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test config-check detects environment variables."""
    monkeypatch.setenv("TABLESLEUTH_CATALOG_NAME", "test_catalog")

    result = cli_runner.invoke(config_check, [])

    assert "TABLESLEUTH_CATALOG_NAME" in result.output


def test_config_check_masks_password_env_var(
    cli_runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test config-check masks password environment variables."""
    monkeypatch.setenv("TABLESLEUTH_GIZMO_PASSWORD", "secret123")

    result = cli_runner.invoke(config_check, [])

    # Password should be masked
    assert "secret123" not in result.output
    if "TABLESLEUTH_GIZMO_PASSWORD" in result.output:
        assert "*" in result.output


# ============================================================================
# Entry Point Tests
# ============================================================================


def test_cli_entry_point_exists() -> None:
    """Test that entry point function exists."""
    from tablesleuth import cli

    assert hasattr(cli, "entry_point")
    assert callable(cli.entry_point)


def test_cli_has_version() -> None:
    """Test that CLI module has version."""
    from tablesleuth import cli

    assert hasattr(cli, "__version__")
    assert cli.__version__
