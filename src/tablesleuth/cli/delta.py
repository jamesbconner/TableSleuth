"""Inspect Delta Lake tables for forensic analysis."""

from __future__ import annotations

import logging
import sys

import click
from textual.app import App

from tablesleuth.config import AppConfig, CatalogConfig, GizmoConfig
from tablesleuth.tui.views.delta_view import DeltaView

from .helpers import configure_logging

logger = logging.getLogger(__name__)


@click.command("delta")
@click.argument("path", type=str)
@click.option(
    "--version",
    type=int,
    default=None,
    help="Load specific version (default: latest)",
)
@click.option(
    "--storage-option",
    multiple=True,
    type=str,
    help="Storage backend options (key=value format, e.g., AWS_REGION=us-west-2)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def delta(
    path: str,
    version: int | None,
    storage_option: tuple[str, ...],
    verbose: bool,
) -> None:
    """Inspect Delta Lake tables for forensic analysis.

    Provides comprehensive analysis including:
    - Version history with operation types and metrics
    - File size distribution and small file detection
    - Storage waste analysis (tombstones, orphaned files)
    - Optimization recommendations
    - Schema evolution tracking
    - DML operation forensics

    PATH can be:

    \b
    - Local Delta table: ./data/events/
    - S3 Delta table: s3://bucket/warehouse/events/
    - Azure Delta table: abfss://container@account.dfs.core.windows.net/path/
    - GCS Delta table: gs://bucket/warehouse/events/

    Examples:

    \b
    # Inspect local Delta table
    tablesleuth delta ./data/events/

    \b
    # Inspect S3 Delta table
    tablesleuth delta s3://my-bucket/warehouse/events/

    \b
    # Load specific version
    tablesleuth delta ./data/events/ --version 42

    \b
    # With custom S3 credentials
    tablesleuth delta s3://bucket/table/ \\
        --storage-option AWS_ACCESS_KEY_ID=xxx \\
        --storage-option AWS_SECRET_ACCESS_KEY=yyy

    \b
    # With AWS profile
    tablesleuth delta s3://bucket/table/ \\
        --storage-option AWS_PROFILE=my-profile

    \b
    # With verbose logging
    tablesleuth delta ./data/events/ --verbose
    """
    # Configure logging
    configure_logging(verbose)

    # Parse storage options from key=value format
    storage_options: dict[str, str] = {}
    for option in storage_option:
        if "=" not in option:
            click.echo(
                f"Error: Invalid storage option format: {option}\n"
                f"Expected format: key=value (e.g., AWS_REGION=us-west-2)",
                err=True,
            )
            sys.exit(1)

        key, value = option.split("=", 1)
        storage_options[key] = value

    if verbose and storage_options:
        click.echo(f"Using storage options: {list(storage_options.keys())}")

    # Load configuration (optional for Delta tables)
    try:
        from tablesleuth.config import load_config

        config = load_config()
    except FileNotFoundError as e:
        click.echo(f"Warning: {e}", err=True)
        click.echo(
            "Using default configuration. Run 'tablesleuth init' to create config files.", err=True
        )
        # Continue with defaults - config is optional for Delta tables
        config = AppConfig(catalog=CatalogConfig(default=None), gizmosql=GizmoConfig())

    try:
        # Import DeltaAdapter here to avoid import errors if deltalake is not installed
        from tablesleuth.services.formats.delta import DeltaAdapter

        # Create Delta adapter with storage options
        adapter = DeltaAdapter(storage_options=storage_options)

        # Open the Delta table
        click.echo(f"Opening Delta table: {path}")
        table_handle = adapter.open_table(path)

        # Load the specified version or latest
        if version is not None:
            click.echo(f"Loading version {version}...")
            snapshot = adapter.load_snapshot(table_handle, version)
        else:
            # Load current version
            click.echo("Loading latest version...")
            snapshot = adapter.load_snapshot(table_handle, None)
            version = snapshot.snapshot_id

        click.echo(f"Loaded version {version} with {len(snapshot.data_files)} data files")

        # Get all snapshots for version history
        click.echo("Loading version history...")
        snapshots = adapter.list_snapshots(table_handle)
        click.echo(f"Found {len(snapshots)} versions (0 to {len(snapshots) - 1})")

        # Launch Delta-specific TUI
        click.echo("Launching TUI...")

        class DeltaViewerApp(App):
            """Wrapper app for DeltaView screen."""

            def on_mount(self) -> None:
                """Push the DeltaView screen on mount."""
                self.push_screen(
                    DeltaView(
                        table_handle=table_handle,
                        adapter=adapter,
                    )
                )

        app = DeltaViewerApp()
        app.run()

    except ImportError as e:
        click.echo(f"Error: Delta Lake support not available: {e}", err=True)
        click.echo("", err=True)
        click.echo("To enable Delta Lake support, install the deltalake package:", err=True)
        click.echo("  pip install deltalake", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: Failed to open Delta table: {e}", err=True)
        if verbose:
            logger.exception("Detailed error information")
        sys.exit(1)
