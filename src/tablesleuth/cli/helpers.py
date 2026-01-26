"""Shared helper functions for CLI commands.

This module contains common functionality used across multiple CLI commands
including error detection, configuration loading, and logging setup.
"""

from __future__ import annotations

import logging
import sys

import click

from tablesleuth.config import AppConfig, load_config

logger = logging.getLogger(__name__)


def configure_logging(verbose: bool) -> None:
    """Configure logging based on verbosity flag.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO level
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Suppress noisy AWS SDK logs
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def load_config_or_exit() -> AppConfig:
    """Load configuration with consistent error handling.

    Returns:
        AppConfig instance

    Exits:
        Exits with code 1 if TABLESLEUTH_CONFIG points to non-existent file
    """
    try:
        return load_config()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("", err=True)
        click.echo(
            "The TABLESLEUTH_CONFIG environment variable points to a non-existent file.",
            err=True,
        )
        click.echo("Either fix the path or unset the variable, then run:", err=True)
        click.echo("  tablesleuth init", err=True)
        sys.exit(1)


def suggest_init_on_config_error(error_msg: str) -> str:
    """Add helpful suggestion to run init command for config-related errors.

    Args:
        error_msg: Original error message

    Returns:
        Enhanced error message with init suggestion
    """
    suggestions = [
        "",
        "Configuration may be missing or incomplete.",
        "Run 'tablesleuth init' to create configuration files,",
        "then edit them to match your environment.",
    ]
    return error_msg + "\n\n" + "\n".join(suggestions)


def is_catalog_error(exception: Exception) -> bool:
    """Check if exception is related to catalog configuration.

    Args:
        exception: Exception to check

    Returns:
        True if error is catalog-related
    """
    error_str = str(exception).lower()
    catalog_keywords = [
        "catalog",
        "pyiceberg",
        "no such catalog",
        "catalog not found",
        "warehouse",
        "metadata",
    ]
    return any(keyword in error_str for keyword in catalog_keywords)


def is_gizmosql_error(exception: Exception) -> bool:
    """Check if exception is related to GizmoSQL connection.

    Args:
        exception: Exception to check

    Returns:
        True if error is GizmoSQL-related
    """
    error_str = str(exception).lower()
    gizmo_keywords = [
        "flightsql",
        "grpc",
        "connection refused",
        "connection error",
        "dial tcp",
        "gizmosql",
    ]
    return any(keyword in error_str for keyword in gizmo_keywords)


def show_gizmosql_help() -> None:
    """Display help message for GizmoSQL connection failures."""
    click.echo("", err=True)
    click.echo("GizmoSQL connection failed. This is optional but required for:", err=True)
    click.echo("  - Column profiling", err=True)
    click.echo("  - Iceberg snapshot performance testing", err=True)
    click.echo("", err=True)
    click.echo("To set up GizmoSQL:", err=True)
    click.echo("  1. Run 'tablesleuth init' to create configuration", err=True)
    click.echo("  2. See docs/GIZMOSQL_DEPLOYMENT_GUIDE.md for installation", err=True)
