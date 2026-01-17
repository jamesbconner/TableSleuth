from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from . import __version__
from .config import load_config
from .models import TableHandle
from .models.file_ref import FileRef
from .services.file_discovery import FileDiscoveryService
from .services.formats.iceberg import IcebergAdapter
from .services.iceberg_metadata_service import IcebergMetadataService
from .services.profiling.gizmo_duckdb import GizmoDuckDbProfiler
from .tui.app import TableSleuthApp
from .tui.views.iceberg_view import IcebergView

logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name="TableSleuth")
def main() -> None:
    """TableSleuth - Parquet File Forensics and Iceberg Snapshot Analysis.

    A powerful TUI for inspecting Parquet files and analyzing Iceberg table snapshots.

    Features:
    - Parquet file inspection (local and S3)
    - Iceberg snapshot analysis and comparison in S3
    - Performance testing between Iceberg snapshots
    - Merge-on-read (MOR) forensics with GizmoSQL (duckdb)
    - Column profiling with GizmoSQL (duckdb)
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

    Provides detailed forensic analysis of Parquet file metadata including schema,
    row groups, column statistics, and data samples. Supports local files, S3 paths,
    and Iceberg table data files.

    PATH can be:

    \b
    - Local Parquet file: data/file.parquet
    - S3 Parquet file: s3://bucket/path/file.parquet
    - Directory: data/warehouse/ (recursively scans for .parquet files)
    - Iceberg table: database.table (requires --catalog, inspects data files)

    Examples:

    \b
    # Inspect a local file
    table-sleuth inspect data/file.parquet

    \b
    # Inspect an S3 file
    table-sleuth inspect s3://bucket/path/file.parquet

    \b
    # Inspect all files in a directory
    table-sleuth inspect data/warehouse/

    \b
    # Inspect Iceberg table data files
    table-sleuth inspect --catalog ratebeer ratebeer.reviews
    """
    # Configure logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Suppress noisy AWS SDK logs
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Load configuration
    config = load_config()
    adapter = IcebergAdapter(default_catalog=config.catalog.default)

    # Detect input type and discover files
    files: list[FileRef] = []
    table_handle: TableHandle | None = None

    try:
        # Check if it's an S3 Tables ARN first
        if path.startswith("arn:aws:s3tables:"):
            click.echo(f"Loading S3 Tables Iceberg table: {path}")

            # Open table using ARN (adapter will parse it)
            table_handle = adapter.open_table(path)

            # Discover files from table
            discovery = FileDiscoveryService(iceberg_adapter=adapter)
            # Extract table identifier from ARN for discovery
            arn_info = adapter._parse_s3_tables_arn(path)
            if arn_info:
                catalog, table_id = arn_info
                files = discovery.discover_from_table(table_id, catalog)
            else:
                click.echo(f"Error: Invalid S3 Tables ARN format: {path}", err=True)
                sys.exit(1)

            click.echo(f"Found {len(files)} data files in table")

        elif catalog_name:
            # Treat as Iceberg table identifier
            click.echo(f"Loading Iceberg table: {path} (catalog: {catalog_name})")

            # Open table
            table_handle = adapter.open_table(path, catalog_name)

            # Discover files from table
            discovery = FileDiscoveryService(iceberg_adapter=adapter)
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


@main.command("iceberg")
@click.argument("metadata_path", type=str, required=False)
@click.option(
    "--catalog",
    "catalog_name",
    type=str,
    default=None,
    help="Catalog name for loading table from catalog.",
)
@click.option(
    "--table",
    "table_identifier",
    type=str,
    default=None,
    help="Table identifier when using --catalog (e.g., 'database.table').",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging.",
)
def iceberg_viewer(
    metadata_path: str | None,
    catalog_name: str | None,
    table_identifier: str | None,
    verbose: bool,
) -> None:
    """Launch Iceberg snapshot analyzer for forensic analysis and performance testing.

    Provides comprehensive analysis of Iceberg table snapshots including metadata,
    file evolution, merge-on-read overhead, and query performance comparison.

    METADATA_PATH: Path to Iceberg metadata.json file (optional if using --catalog)

    \b
    Usage:
    - From metadata file: table-sleuth iceberg /path/to/metadata.json
    - From catalog: table-sleuth iceberg --catalog CATALOG --table database.table

    Features:

    \b
    - Browse all snapshots with operation types and timestamps
    - View snapshot details (data files, delete files, schema, properties)
    - Analyze merge-on-read (MOR) overhead and compaction needs
    - Compare two snapshots side-by-side (file/record changes)
    - Performance test queries between snapshots
    - Preview data samples from snapshots

    Examples:

    \b
    # View snapshots from Glue catalog
    table-sleuth iceberg --catalog ratebeer --table ratebeer.reviews

    \b
    # View snapshots from S3 Tables catalog
    table-sleuth iceberg --catalog tpch --table tpch.lineitem

    \b
    # View from metadata file (local or S3)
    table-sleuth iceberg s3://bucket/warehouse/table/metadata/metadata.json

    \b
    # View with verbose logging (shows debug info)
    table-sleuth iceberg --catalog ratebeer --table ratebeer.reviews -v
    """
    # Configure logging
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Suppress noisy AWS SDK logs
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Load configuration
    config = load_config()

    try:
        # Initialize services
        metadata_service = IcebergMetadataService()

        # Initialize profiler for performance testing
        try:
            profiler = GizmoDuckDbProfiler(
                uri=config.gizmosql.uri,
                username=config.gizmosql.username,
                password=config.gizmosql.password,
                tls_skip_verify=config.gizmosql.tls_skip_verify,
            )
        except Exception as e:
            click.echo(
                f"Warning: Could not initialize profiler: {e}. Performance testing will be disabled.",
                err=True,
            )
            profiler = None

        # Load table
        if catalog_name and table_identifier:
            # Load from catalog
            click.echo(f"Loading Iceberg table: {table_identifier} (catalog: {catalog_name})")
            table_info = metadata_service.load_table(
                catalog_name=catalog_name, table_identifier=table_identifier
            )
        elif metadata_path:
            # Load from metadata file path
            metadata_file = Path(metadata_path)
            if not metadata_file.exists():
                click.echo(f"Error: Metadata file not found: {metadata_path}", err=True)
                sys.exit(1)

            click.echo(f"Loading Iceberg table from metadata: {metadata_path}")
            table_info = metadata_service.load_table(metadata_path=str(metadata_file))
        else:
            # Neither provided
            click.echo(
                "Error: Must provide either METADATA_PATH or both --catalog and --table",
                err=True,
            )
            click.echo("Try 'table-sleuth iceberg --help' for more information.", err=True)
            sys.exit(1)

        click.echo(f"Table UUID: {table_info.table_uuid}")
        click.echo(f"Format version: {table_info.format_version}")
        click.echo(f"Location: {table_info.location}")

        # Create and run Iceberg viewer
        from textual.app import App

        class IcebergViewerApp(App):
            """Wrapper app for IcebergView screen."""

            def on_mount(self) -> None:
                """Push the IcebergView screen on mount."""
                self.push_screen(
                    IcebergView(
                        table_info=table_info,
                        metadata_service=metadata_service,
                        profiler=profiler,
                        catalog_name=catalog_name,
                    )
                )

        app = IcebergViewerApp()
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


def entry_point() -> None:
    """Entry point for the CLI."""
    main()


if __name__ == "__main__":
    entry_point()
