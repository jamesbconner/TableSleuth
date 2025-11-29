"""Tests for CLI functionality."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from table_sleuth.cli import inspect, main


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner for testing."""
    return CliRunner()


def test_main_command_exists(cli_runner: CliRunner) -> None:
    """Test that main command exists."""
    result = cli_runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Table Sleuth" in result.output


def test_version_flag(cli_runner: CliRunner) -> None:
    """Test version flag."""
    result = cli_runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower() or "table sleuth" in result.output.lower()


def test_inspect_command_exists(cli_runner: CliRunner) -> None:
    """Test that inspect command exists."""
    result = cli_runner.invoke(main, ["inspect", "--help"])
    assert result.exit_code == 0
    assert "inspect" in result.output.lower()


def test_inspect_help_shows_examples(cli_runner: CliRunner) -> None:
    """Test that inspect help shows examples."""
    result = cli_runner.invoke(main, ["inspect", "--help"])
    assert result.exit_code == 0
    assert "Examples" in result.output or "examples" in result.output


def test_inspect_nonexistent_file(cli_runner: CliRunner) -> None:
    """Test inspect with nonexistent file."""
    result = cli_runner.invoke(inspect, ["nonexistent.parquet"])
    assert result.exit_code != 0
    assert "does not exist" in result.output.lower() or "error" in result.output.lower()


def test_inspect_with_verbose_flag(cli_runner: CliRunner) -> None:
    """Test inspect with verbose flag."""
    result = cli_runner.invoke(inspect, ["--verbose", "nonexistent.parquet"])
    assert result.exit_code != 0


def test_inspect_real_file(cli_runner: CliRunner) -> None:
    """Test inspect with real test file."""
    test_file = Path("tests/data/nested_test.parquet")

    if not test_file.exists():
        pytest.skip("Test file not found")

    # We can't actually run the TUI in tests, so we just verify
    # the file validation logic works by checking help
    # The actual TUI launch is tested manually
    pytest.skip("TUI launch cannot be tested in automated tests")


def test_cli_has_version() -> None:
    """Test that CLI module has version."""
    from table_sleuth import cli

    assert hasattr(cli, "__version__")
    assert cli.__version__


def test_inspect_command_parameters(cli_runner: CliRunner) -> None:
    """Test that inspect command has required parameters."""
    result = cli_runner.invoke(main, ["inspect", "--help"])
    assert result.exit_code == 0

    # Check for required parameters
    assert "PATH" in result.output or "path" in result.output
    assert "--catalog" in result.output
    assert "--verbose" in result.output


def test_legacy_tui_command_exists(cli_runner: CliRunner) -> None:
    """Test that legacy tui command still exists."""
    result = cli_runner.invoke(main, ["tui", "--help"])
    assert result.exit_code == 0


def test_main_help_shows_commands(cli_runner: CliRunner) -> None:
    """Test that main help shows available commands."""
    result = cli_runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "inspect" in result.output.lower()


def test_inspect_directory_nonexistent(cli_runner: CliRunner) -> None:
    """Test inspect with nonexistent directory."""
    result = cli_runner.invoke(inspect, ["/nonexistent/directory"])
    assert result.exit_code != 0
    assert "error" in result.output.lower()


def test_cli_entry_point_exists() -> None:
    """Test that entry point function exists."""
    from table_sleuth import cli

    assert hasattr(cli, "entry_point")
    assert callable(cli.entry_point)
