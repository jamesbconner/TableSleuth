from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from .config import load_config
from .models import TableHandle
from .models.file_ref import FileRef
from .services.file_discovery import FileDiscoveryService
from .services.formats.iceberg import IcebergAdapter
from .tui.app import TableSleuthApp

logger = logging.getLogger(__name__)

# Version information
__version__ = "0.1.0-mvp0"


@click.group()
@click.version_option(version=__version__, prog_name="Table Sleuth")
def main() -> None:
    """Table Sleuth - Parquet File Forensics Tool.

    MVP 0: File-Based Inspection

    Inspect Parquet files, directories, or Iceberg tables with a powerful TUI.
    """


@main.command("inspect")
@click.argument("path", type=str)
@click.option(
    "--catalog",
    "catalog_name",
    type=str,
    default=None,
    help="Catalog name for Iceberg tables (e.g., 'local'). If provided, PATH is treated as a table identifier.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging.",
)
def inspect(path: str, catalog_name: str | None, verbose: bool) -> None:
    """Inspect Parquet files, directories, or Iceberg tables.

    PATH can be:

    \b
    - A single Parquet file: /path/to/file.parquet
    - A directory: /path/to/directory (recursively scans for .parquet files)
    - An Iceberg table: database.table (requires --catalog option)

    Examples:

    \b
    # Inspect a single file
    table-sleuth inspect data/file.parquet

    \b
    # Inspect all files in a directory
    table-sleuth inspect data/warehouse/

    \b
    # Inspect an Iceberg table
    table-sleuth inspect ratebeer.reviews --catalog local
    """
    # Configure logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Load configuration
    config = load_config()
    adapter = IcebergAdapter(default_catalog=config.catalog.default)

    # Detect input type and discover files
    files: list[FileRef] = []
    table_handle: TableHandle | None = None

    try:
        if catalog_name:
            # Treat as Iceberg table identifier
            click.echo(f"Loading Iceberg table: {path} (catalog: {catalog_name})")

            # Open table
            table_handle = adapter.open_table(path, catalog_name)

            # Discover files from table
            discovery = FileDiscoveryService()
            files = discovery.discover_from_table(path, catalog_name)

            click.echo(f"Found {len(files)} data files in table")

        else:
            # Treat as file or directory path
            path_obj = Path(path)

            if not path_obj.exists():
                click.echo(f"Error: Path does not exist: {path}", err=True)
                sys.exit(1)

            if path_obj.is_file():
                # Single file
                if not path.endswith((".parquet", ".pq")):
                    click.echo(
                        f"Warning: File does not have .parquet extension: {path}",
                        err=True,
                    )

                click.echo(f"Loading Parquet file: {path}")
                discovery = FileDiscoveryService()
                files = discovery.discover_from_path(path)

            elif path_obj.is_dir():
                # Directory
                click.echo(f"Scanning directory: {path}")
                discovery = FileDiscoveryService()
                files = discovery.discover_from_path(path)
                click.echo(f"Found {len(files)} Parquet files")

            else:
                click.echo(f"Error: Path is neither a file nor directory: {path}", err=True)
                sys.exit(1)

            # Create a dummy table handle for file-based inspection
            table_handle = TableHandle(native=None, format_name="parquet")

        if not files:
            click.echo("Error: No Parquet files found", err=True)
            sys.exit(1)

        # Launch TUI
        click.echo(f"Launching TUI with {len(files)} file(s)...")
        app = TableSleuthApp(
            table_handle=table_handle,
            adapter=adapter,
            config=config,
            files=files,
        )
        app.run()

    except FileNotFoundError as e:
        click.echo(f"Error: File not found: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: Invalid input: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            logger.exception("Detailed error information")
        sys.exit(1)


# Legacy command for backward compatibility
@main.command("tui")
@click.argument("identifier", type=str)
@click.option(
    "--catalog",
    "catalog_name",
    type=str,
    default=None,
    help="Catalog name (for example local). If omitted, identifier is treated as a path.",
)
def run_tui(identifier: str, catalog_name: str | None) -> None:
    """Launch the Textual TUI (legacy command, use 'inspect' instead)."""
    click.echo("Note: 'tui' command is deprecated, use 'inspect' instead", err=True)

    # Forward to inspect command
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(
        inspect, [identifier] + (["--catalog", catalog_name] if catalog_name else [])
    )
    sys.exit(result.exit_code)


def entry_point() -> None:
    """Entry point for the CLI."""
    main()


if __name__ == "__main__":
    entry_point()
