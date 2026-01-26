"""TableSleuth CLI entry point with auto-loading command modules.

This module provides the main CLI group and automatically discovers and
registers command modules from the cli/ directory.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import click

from tablesleuth import __version__

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="TableSleuth")
def main() -> None:
    """TableSleuth - Parquet File Forensics and Table Format Analysis.

    A powerful TUI for inspecting Parquet files and analyzing table formats.

    Features:
    - Parquet file inspection (local and S3)
    - Iceberg snapshot analysis and comparison
    - Delta Lake version history and forensics
    - Performance testing between snapshots
    - Merge-on-read (MOR) forensics with GizmoSQL (duckdb)
    - Column profiling with GizmoSQL (duckdb)
    """


# Dynamic discovery: auto-register all CLI commands from cli/ directory
COMMAND_DIR = Path(__file__).parent
if COMMAND_DIR.exists():
    for filepath in COMMAND_DIR.iterdir():
        # Only import .py files that are not __init__.py or helpers.py
        if filepath.suffix == ".py" and filepath.stem not in ("__init__", "helpers"):
            command_name = filepath.stem
            module_name = f"tablesleuth.cli.{command_name}"
            
            try:
                module = importlib.import_module(module_name)
                # Look for a function with the same name as the module (or with underscores replaced)
                cli_function = getattr(module, command_name, None)
                
                if cli_function and callable(cli_function):
                    main.add_command(cli_function)
                    logger.debug(f"Registered command: {command_name}")
                else:
                    logger.debug(f"No command function found in {module_name}")
            except Exception as e:
                logger.debug(f"Failed to import {module_name}: {e}")


def entry_point() -> None:
    """Entry point for the CLI."""
    main()


# Import command functions for backward compatibility with tests
from .config_check import config_check  # noqa: E402
from .delta import delta  # noqa: E402
from .iceberg import iceberg as iceberg_viewer  # noqa: E402
from .init import init as init_config  # noqa: E402
from .parquet import parquet  # noqa: E402

# Import helper functions for backward compatibility with tests
from .helpers import (  # noqa: E402
    is_catalog_error as _is_catalog_error,
    is_gizmosql_error as _is_gizmosql_error,
    suggest_init_on_config_error as _suggest_init_on_config_error,
)

__all__ = [
    "main",
    "entry_point",
    "config_check",
    "delta",
    "iceberg_viewer",
    "init_config",
    "parquet",
    "_is_catalog_error",
    "_is_gizmosql_error",
    "_suggest_init_on_config_error",
]
