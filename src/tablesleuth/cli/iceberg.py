"""Launch Iceberg snapshot analyzer for forensic analysis and performance testing."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from textual.app import App

from tablesleuth.services.iceberg_metadata_service import IcebergMetadataService
from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler
from tablesleuth.tui.views.iceberg_view import IcebergView

from .helpers import (
    configure_logging,
    is_catalog_error,
    is_gizmosql_error,
    load_config_or_exit,
    show_gizmosql_help,
    suggest_init_on_config_error,
)

logger = logging.getLogger(__name__)


@click.command("iceberg")
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
def iceberg(
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
    - From metadata file: tablesleuth iceberg /path/to/metadata.json
    - From catalog: tablesleuth iceberg --catalog CATALOG --table database.table

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
    tablesleuth iceberg --catalog ratebeer --table ratebeer.reviews

    \b
    # View snapshots from S3 Tables catalog
    tablesleuth iceberg --catalog tpch --table tpch.lineitem

    \b
    # View from metadata file (local or S3)
    tablesleuth iceberg s3://bucket/warehouse/table/metadata/metadata.json

    \b
    # View with verbose logging (shows debug info)
    tablesleuth iceberg --catalog ratebeer --table ratebeer.reviews -v
    """
    # Configure logging
    configure_logging(verbose)

    # Load configuration
    config = load_config_or_exit()

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
            click.echo("Try 'tablesleuth iceberg --help' for more information.", err=True)
            sys.exit(1)

        click.echo(f"Table UUID: {table_info.table_uuid}")
        click.echo(f"Format version: {table_info.format_version}")
        click.echo(f"Location: {table_info.location}")

        # Create and run Iceberg viewer
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
