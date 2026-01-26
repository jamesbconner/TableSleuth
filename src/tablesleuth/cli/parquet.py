"""Inspect Parquet metadata in files, directories, or tables."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from tablesleuth.models import TableHandle
from tablesleuth.models.file_ref import FileRef
from tablesleuth.services.file_discovery import FileDiscoveryService
from tablesleuth.services.formats.iceberg import IcebergAdapter
from tablesleuth.tui.app import TableSleuthApp

from .helpers import (
    configure_logging,
    is_catalog_error,
    is_gizmosql_error,
    load_config_or_exit,
    show_gizmosql_help,
    suggest_init_on_config_error,
)

logger = logging.getLogger(__name__)


@click.command("parquet")
@click.argument("path", type=str)
@click.option(
    "--catalog",
    "catalog_name",
    type=str,
    default=None,
    help="Catalog name for Iceberg tables (e.g., 'local'). If provided, PATH is treated as a table identifier.",
)
@click.option(
    "--region",
    type=str,
    default=None,
    help="AWS region for Glue catalog queries. Defaults to AWS_REGION, AWS_DEFAULT_REGION, or us-east-2.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging.",
)
def parquet(path: str, catalog_name: str | None, region: str | None, verbose: bool) -> None:
    """Inspect Parquet metadata in files, directories, or tables.

    Provides detailed forensic analysis of Parquet file metadata including schema,
    row groups, column statistics, and data samples. Supports local files, S3 paths,
    Iceberg tables, and Glue Hive tables.

    PATH can be:

    \b
    - Local Parquet file: data/file.parquet
    - S3 Parquet file: s3://bucket/path/file.parquet
    - Directory: data/warehouse/ (recursively scans for .parquet files)
    - Iceberg table: database.table (requires --catalog, inspects data files)
    - Glue Hive table: database.table (requires --catalog, auto-detects if not in .pyiceberg.yaml)

    Examples:

    \b
    # Inspect a local file
    tablesleuth parquet data/file.parquet

    \b
    # Inspect an S3 file
    tablesleuth parquet s3://bucket/path/file.parquet

    \b
    # Inspect all files in a directory
    tablesleuth parquet data/warehouse/

    \b
    # Inspect Iceberg table data files
    tablesleuth parquet --catalog ratebeer ratebeer.reviews

    \b
    # Inspect Glue Hive table (auto-detects if not in .pyiceberg.yaml)
    tablesleuth parquet --catalog mydb mydb.mytable

    \b
    # Specify AWS region for Glue catalog queries
    tablesleuth parquet --catalog mydb --region us-east-2 mydb.mytable
    """
    # Configure logging
    configure_logging(verbose)

    # Load configuration
    config = load_config_or_exit()

    adapter = IcebergAdapter(default_catalog=config.catalog.default)

    # Detect input type and discover files
    files: list[FileRef] = []
    table_handle: TableHandle | None = None

    try:
        # Check if it's an S3 Tables ARN first
        if path.startswith("arn:aws:s3tables:"):
            files, table_handle = _handle_s3_tables_arn(path, catalog_name, adapter, region)

        elif catalog_name:
            # Treat as Iceberg table identifier (or Glue Hive table as fallback)
            files, table_handle = _handle_catalog_table(path, catalog_name, adapter, region)

        else:
            # Treat as file or directory path (local or S3)
            files, table_handle = _handle_file_or_directory(path, region)

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
        if is_catalog_error(e):
            click.echo(suggest_init_on_config_error(""), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if is_catalog_error(e):
            click.echo(suggest_init_on_config_error(""), err=True)
        elif is_gizmosql_error(e):
            show_gizmosql_help()
        if verbose:
            logger.exception("Detailed error information")
        sys.exit(1)


def _handle_s3_tables_arn(
    path: str,
    catalog_name: str | None,
    adapter: IcebergAdapter,
    region: str | None,
) -> tuple[list[FileRef], TableHandle]:
    """Handle S3 Tables ARN path.

    Args:
        path: S3 Tables ARN
        catalog_name: Optional catalog name
        adapter: IcebergAdapter instance
        region: Optional AWS region

    Returns:
        Tuple of (files, table_handle)
    """
    click.echo(f"Loading S3 Tables Iceberg table: {path}")

    # Open table using ARN (adapter will parse it)
    table_handle = adapter.open_table(path, catalog_name)

    # Discover files from table
    discovery = FileDiscoveryService(iceberg_adapter=adapter, region=region)

    # Extract table identifier from ARN for discovery
    arn_info = adapter._parse_s3_tables_arn(path, catalog_name)
    if arn_info:
        catalog, table_id = arn_info
        files = discovery.discover_from_table(table_id, catalog)
    else:
        click.echo(f"Error: Invalid S3 Tables ARN format: {path}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(files)} data files in table")
    return files, table_handle


def _handle_catalog_table(
    path: str,
    catalog_name: str,
    adapter: IcebergAdapter,
    region: str | None,
) -> tuple[list[FileRef], TableHandle]:
    """Handle catalog table identifier.

    Args:
        path: Table identifier
        catalog_name: Catalog name
        adapter: IcebergAdapter instance
        region: Optional AWS region

    Returns:
        Tuple of (files, table_handle)
    """
    click.echo(f"Loading table: {path} (catalog: {catalog_name})")

    # Initialize discovery service with region
    discovery = FileDiscoveryService(iceberg_adapter=adapter, region=region)

    try:
        # Try Iceberg first
        table_handle = adapter.open_table(path, catalog_name)
        files = discovery.discover_from_table(path, catalog_name)
        click.echo(f"Found {len(files)} data files in Iceberg table")
        return files, table_handle

    except Exception as iceberg_error:
        # Check if it's specifically a catalog configuration error
        error_msg = str(iceberg_error).lower()
        catalog_name_lower = catalog_name.lower()

        # Specific patterns that indicate catalog is not configured
        is_catalog_missing = (
            "no such catalog" in error_msg
            or "catalog not found" in error_msg
            or f"catalog '{catalog_name_lower}' does not exist" in error_msg
            or f"catalog {catalog_name_lower} does not exist" in error_msg
            or "uri missing" in error_msg
        )

        if is_catalog_missing:
            # Try Glue Hive table fallback
            return _try_glue_fallback(path, catalog_name, discovery, iceberg_error)
        else:
            # Some other error (e.g., table not found in configured catalog)
            raise


def _try_glue_fallback(
    path: str,
    catalog_name: str,
    discovery: FileDiscoveryService,
    iceberg_error: Exception,
) -> tuple[list[FileRef], TableHandle]:
    """Try Glue Hive table as fallback.

    Args:
        path: Table identifier
        catalog_name: Catalog/database name
        discovery: FileDiscoveryService instance
        iceberg_error: Original Iceberg error

    Returns:
        Tuple of (files, table_handle)

    Raises:
        SystemExit: If both Iceberg and Glue attempts fail
    """
    click.echo(f"Catalog '{catalog_name}' not in .pyiceberg.yaml, trying Glue database...")

    try:
        files = discovery.discover_from_glue_database(catalog_name, path)
        click.echo(f"Found {len(files)} Parquet files in Glue Hive table")

        # Create a dummy table handle for Hive table
        table_handle = TableHandle(native=None, format_name="parquet")
        return files, table_handle

    except Exception as glue_error:
        # Both failed, provide helpful error
        click.echo(f"Error: Could not load table '{path}'", err=True)
        click.echo("", err=True)
        click.echo("Tried:", err=True)
        click.echo(
            f"  1. Iceberg catalog '{catalog_name}' in .pyiceberg.yaml: {iceberg_error}",
            err=True,
        )
        click.echo(f"  2. Glue database '{catalog_name}': {glue_error}", err=True)
        click.echo("", err=True)
        click.echo("Suggestions:", err=True)
        click.echo("  - For Iceberg tables: Add catalog to .pyiceberg.yaml", err=True)
        click.echo(
            "  - For Glue tables: Verify table exists with 'aws glue get-table'",
            err=True,
        )
        click.echo(
            f"  - Try different region with --region flag (current: {discovery._resolved_region})",
            err=True,
        )
        sys.exit(1)


def _handle_file_or_directory(
    path: str,
    region: str | None,
) -> tuple[list[FileRef], TableHandle]:
    """Handle file or directory path.

    Args:
        path: File or directory path (local or S3)
        region: Optional AWS region

    Returns:
        Tuple of (files, table_handle)
    """
    # Check if it's an S3 path (both s3:// and s3a:// schemes)
    if path.startswith("s3://") or path.startswith("s3a://"):
        click.echo(f"Loading from S3: {path}")
        discovery = FileDiscoveryService(region=region)
        files = discovery.discover_from_path(path)

        if len(files) == 1:
            click.echo("Found 1 Parquet file")
        else:
            click.echo(f"Found {len(files)} Parquet files")
    else:
        # Local path
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
    return files, table_handle
