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


__all__ = [
    "main",
    "entry_point",
]
