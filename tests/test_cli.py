"""Tests for CLI functionality."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from tablesleuth.cli import main, parquet


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


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


def test_parquet_real_file(cli_runner: CliRunner, sample_parquet_file: Path) -> None:
    """Test parquet with real test file."""
    # We can't actually run the TUI in tests, so we just verify
    # the file validation logic works by checking help
    # The actual TUI launch is tested manually
    pytest.skip("TUI launch cannot be tested in automated tests")


def test_cli_has_version() -> None:
    """Test that CLI module has version."""
    from tablesleuth import cli

    assert hasattr(cli, "__version__")
    assert cli.__version__


def test_parquet_command_parameters(cli_runner: CliRunner) -> None:
    """Test that parquet command has required parameters."""
    result = cli_runner.invoke(main, ["parquet", "--help"])
    assert result.exit_code == 0

    # Check for required parameters
    assert "PATH" in result.output or "path" in result.output
    assert "--catalog" in result.output
    assert "--verbose" in result.output


def test_main_help_shows_commands(cli_runner: CliRunner) -> None:
    """Test that main help shows available commands."""
    result = cli_runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "parquet" in result.output.lower()


def test_parquet_directory_nonexistent(cli_runner: CliRunner) -> None:
    """Test parquet with nonexistent directory."""
    result = cli_runner.invoke(parquet, ["/nonexistent/directory"])
    assert result.exit_code != 0
    assert "error" in result.output.lower()


def test_cli_entry_point_exists() -> None:
    """Test that entry point function exists."""
    from tablesleuth import cli

    assert hasattr(cli, "entry_point")
    assert callable(cli.entry_point)
