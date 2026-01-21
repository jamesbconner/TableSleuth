from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import click
import yaml

from . import __version__
from .config import get_config_file_path, load_config
from .models import TableHandle
from .models.file_ref import FileRef
from .services.file_discovery import FileDiscoveryService
from .services.formats.iceberg import IcebergAdapter
from .services.iceberg_metadata_service import IcebergMetadataService
from .services.profiling.gizmo_duckdb import GizmoDuckDbProfiler
from .tui.app import TableSleuthApp
from .tui.views.iceberg_view import IcebergView
from .utils.config_templates import get_pyiceberg_template, get_tablesleuth_template

logger = logging.getLogger(__name__)


def _suggest_init_on_config_error(error_msg: str) -> str:
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


def _is_catalog_error(exception: Exception) -> bool:
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


def _is_gizmosql_error(exception: Exception) -> bool:
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


@main.command("parquet")
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
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Suppress noisy AWS SDK logs
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Load configuration
    try:
        config = load_config()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("", err=True)
        click.echo(
            "The TABLESLEUTH_CONFIG environment variable points to a non-existent file.", err=True
        )
        click.echo("Either fix the path or unset the variable, then run:", err=True)
        click.echo("  tablesleuth init", err=True)
        sys.exit(1)

    adapter = IcebergAdapter(default_catalog=config.catalog.default)

    # Detect input type and discover files
    files: list[FileRef] = []
    table_handle: TableHandle | None = None

    try:
        # Check if it's an S3 Tables ARN first
        if path.startswith("arn:aws:s3tables:"):
            click.echo(f"Loading S3 Tables Iceberg table: {path}")

            # Open table using ARN (adapter will parse it)
            # Pass catalog_name to allow user to specify which S3 Tables catalog to use
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

        elif catalog_name:
            # Treat as Iceberg table identifier (or Glue Hive table as fallback)
            click.echo(f"Loading table: {path} (catalog: {catalog_name})")

            # Initialize discovery service with region
            discovery = FileDiscoveryService(iceberg_adapter=adapter, region=region)

            try:
                # Try Iceberg first
                table_handle = adapter.open_table(path, catalog_name)
                files = discovery.discover_from_table(path, catalog_name)
                click.echo(f"Found {len(files)} data files in Iceberg table")

            except Exception as iceberg_error:
                # Check if it's specifically a catalog configuration error
                # Only trigger Glue fallback if the catalog itself is not configured
                error_msg = str(iceberg_error).lower()
                catalog_name_lower = catalog_name.lower()

                # Specific patterns that indicate catalog is not configured
                is_catalog_missing = (
                    "no such catalog" in error_msg
                    or "catalog not found" in error_msg
                    or f"catalog '{catalog_name_lower}' does not exist" in error_msg
                    or f"catalog {catalog_name_lower} does not exist" in error_msg
                    or "uri missing" in error_msg  # PyIceberg error when catalog not configured
                )

                if is_catalog_missing:
                    # Try Glue Hive table fallback
                    click.echo(
                        f"Catalog '{catalog_name}' not in .pyiceberg.yaml, trying Glue database..."
                    )

                    try:
                        files = discovery.discover_from_glue_database(catalog_name, path)
                        click.echo(f"Found {len(files)} Parquet files in Glue Hive table")

                        # Create a dummy table handle for Hive table
                        table_handle = TableHandle(native=None, format_name="parquet")

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
                        click.echo(
                            "  - For Iceberg tables: Add catalog to .pyiceberg.yaml", err=True
                        )
                        click.echo(
                            "  - For Glue tables: Verify table exists with 'aws glue get-table'",
                            err=True,
                        )
                        click.echo(
                            f"  - Try different region with --region flag (current: {discovery._resolved_region})",
                            err=True,
                        )
                        sys.exit(1)
                else:
                    # Some other error (e.g., table not found in configured catalog)
                    # Don't try Glue fallback, just report the error
                    raise

        else:
            # Treat as file or directory path (local or S3)

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
        if _is_catalog_error(e):
            click.echo(_suggest_init_on_config_error(""), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if _is_catalog_error(e):
            click.echo(_suggest_init_on_config_error(""), err=True)
        elif _is_gizmosql_error(e):
            click.echo("", err=True)
            click.echo("GizmoSQL connection failed. This is optional but required for:", err=True)
            click.echo("  - Column profiling", err=True)
            click.echo("  - Iceberg snapshot performance testing", err=True)
            click.echo("", err=True)
            click.echo("To set up GizmoSQL:", err=True)
            click.echo("  1. Run 'tablesleuth init' to create configuration", err=True)
            click.echo("  2. See docs/GIZMOSQL_DEPLOYMENT_GUIDE.md for installation", err=True)
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
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Suppress noisy AWS SDK logs
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Load configuration
    try:
        config = load_config()
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("", err=True)
        click.echo(
            "The TABLESLEUTH_CONFIG environment variable points to a non-existent file.", err=True
        )
        click.echo("Either fix the path or unset the variable, then run:", err=True)
        click.echo("  tablesleuth init", err=True)
        sys.exit(1)

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
        if _is_catalog_error(e):
            click.echo(_suggest_init_on_config_error(""), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if _is_catalog_error(e):
            click.echo(_suggest_init_on_config_error(""), err=True)
        elif _is_gizmosql_error(e):
            click.echo("", err=True)
            click.echo("GizmoSQL connection failed. This is optional but required for:", err=True)
            click.echo("  - Iceberg snapshot performance testing", err=True)
            click.echo("", err=True)
            click.echo("To set up GizmoSQL:", err=True)
            click.echo("  1. Run 'tablesleuth init' to create configuration", err=True)
            click.echo("  2. See docs/GIZMOSQL_DEPLOYMENT_GUIDE.md for installation", err=True)
        if verbose:
            logger.exception("Detailed error information")
        sys.exit(1)


@main.command("delta")
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
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Suppress noisy AWS SDK logs
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

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

    # Load configuration
    try:
        config = load_config()
    except FileNotFoundError as e:
        click.echo(f"Warning: {e}", err=True)
        click.echo(
            "Using default configuration. Run 'tablesleuth init' to create config files.", err=True
        )
        # Continue with defaults - config is optional for Delta tables
        from .config import AppConfig, CatalogConfig, GizmoConfig

        config = AppConfig(catalog=CatalogConfig(default=None), gizmosql=GizmoConfig())

    try:
        # Import DeltaAdapter here to avoid import errors if deltalake is not installed
        from .services.formats.delta import DeltaAdapter

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
        from textual.app import App

        from .tui.views.delta_view import DeltaView

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


@main.command("init")
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing configuration files.",
)
def init_config(force: bool) -> None:
    """Initialize TableSleuth configuration files.

    Creates configuration files with comprehensive templates and examples:
    - tablesleuth.toml: Main TableSleuth configuration
    - .pyiceberg.yaml: PyIceberg catalog configuration

    You will be prompted to choose between:
    - Home directory (~/) - User-level configuration
    - Current directory (./) - Project-level configuration

    Configuration priority (highest to lowest):
    1. Environment variables
    2. Local config files (./tablesleuth.toml, ./.pyiceberg.yaml)
    3. Home config files (~/tablesleuth.toml, ~/.pyiceberg.yaml)
    4. Built-in defaults

    Examples:

    \b
    # Initialize config files (interactive prompt for location)
    tablesleuth init

    \b
    # Force overwrite existing files
    tablesleuth init --force
    """
    click.echo("TableSleuth Configuration Initialization")
    click.echo("=" * 50)
    click.echo()

    # Prompt for location
    click.echo("Where would you like to create configuration files?")
    click.echo()
    click.echo("  1. Home directory (~/) - User-level configuration")
    click.echo("     Files: ~/tablesleuth.toml, ~/.pyiceberg.yaml")
    click.echo("     Use for: Personal settings across all projects")
    click.echo()
    click.echo("  2. Current directory (./) - Project-level configuration")
    click.echo("     Files: ./tablesleuth.toml, ./.pyiceberg.yaml")
    click.echo("     Use for: Project-specific settings")
    click.echo()

    choice = click.prompt(
        "Enter your choice",
        type=click.Choice(["1", "2"]),
        default="1",
    )

    if choice == "1":
        base_path = Path.home()
        location_name = "home directory"
    else:
        base_path = Path.cwd()
        location_name = "current directory"

    click.echo()
    click.echo(f"Creating configuration files in {location_name}...")
    click.echo()

    # Define file paths
    tablesleuth_config = base_path / "tablesleuth.toml"
    pyiceberg_config = base_path / ".pyiceberg.yaml"

    files_to_create = [
        (tablesleuth_config, get_tablesleuth_template(), "tablesleuth.toml"),
        (pyiceberg_config, get_pyiceberg_template(), ".pyiceberg.yaml"),
    ]

    # Check for existing files
    existing_files = [path for path, _, _ in files_to_create if path.exists()]

    if existing_files and not force:
        click.echo("Error: Configuration files already exist:", err=True)
        for path in existing_files:
            click.echo(f"  - {path}", err=True)
        click.echo()
        click.echo("Use --force to overwrite existing files.", err=True)
        sys.exit(1)

    # Create files
    created_files = []
    for path, content, name in files_to_create:
        try:
            path.write_text(content, encoding="utf-8")
            created_files.append(path)
            click.echo(f"  ✓ Created {path}")
        except Exception as e:
            click.echo(f"  ✗ Failed to create {name}: {e}", err=True)
            sys.exit(1)

    click.echo()
    click.echo("Configuration files created successfully!")
    click.echo()
    click.echo("Next steps:")
    click.echo()
    click.echo("1. Edit the configuration files to match your environment:")
    for path in created_files:
        click.echo(f"   {path}")
    click.echo()
    click.echo("2. For Iceberg catalogs, configure .pyiceberg.yaml with your catalog details")
    click.echo("   See: https://py.iceberg.apache.org/configuration/")
    click.echo()
    click.echo("3. For GizmoSQL profiling, install and start the GizmoSQL server")
    click.echo("   See: docs/GIZMOSQL_DEPLOYMENT_GUIDE.md")
    click.echo()
    click.echo("4. Verify your configuration:")
    click.echo("   tablesleuth config-check")
    click.echo()


@main.command("config-check")
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed configuration values.",
)
@click.option(
    "--with-gizmosql",
    is_flag=True,
    help="Include GizmoSQL connection test (optional component).",
)
def config_check(verbose: bool, with_gizmosql: bool) -> None:
    """Check TableSleuth configuration and validate settings.

    Validates configuration files and tests connections to verify setup.
    Shows which configuration files are being used and reports any issues.

    Checks performed:
    - Configuration file locations and syntax
    - Environment variable overrides
    - PyIceberg catalog configuration
    - GizmoSQL connection (only with --with-gizmosql flag)

    Examples:

    \b
    # Quick check (pass/fail)
    tablesleuth config-check

    \b
    # Detailed check with all values
    tablesleuth config-check --verbose

    \b
    # Include optional GizmoSQL connection test
    tablesleuth config-check --with-gizmosql
    """
    click.echo("TableSleuth Configuration Check")
    click.echo("=" * 50)
    click.echo()

    all_checks_passed = True

    # Check 1: TableSleuth configuration file
    click.echo("1. TableSleuth Configuration (tablesleuth.toml)")
    click.echo("-" * 50)

    config_path = None
    config_path_error = False

    try:
        config_path = get_config_file_path()
    except FileNotFoundError as e:
        click.echo(f"   ✗ Error: {e}", err=True)
        click.echo(
            "     The TABLESLEUTH_CONFIG environment variable points to a non-existent file",
            err=True,
        )
        click.echo("     Either fix the path or unset the variable", err=True)
        all_checks_passed = False
        config_path_error = True

    if config_path:
        click.echo(f"   ✓ Config file found: {config_path}")

        try:
            config = load_config()
            click.echo("   ✓ Config file syntax valid")

            if verbose:
                click.echo()
                click.echo("   Configuration values:")
                click.echo(f"     catalog.default: {config.catalog.default or '(not set)'}")
                click.echo(f"     gizmosql.uri: {config.gizmosql.uri}")
                click.echo(f"     gizmosql.username: {config.gizmosql.username}")
                click.echo(f"     gizmosql.password: {'*' * len(config.gizmosql.password)}")
                click.echo(f"     gizmosql.tls_skip_verify: {config.gizmosql.tls_skip_verify}")
        except Exception as e:
            click.echo(f"   ✗ Config file error: {e}", err=True)
            all_checks_passed = False
    elif not config_path_error:
        # Only show "no config found" if there wasn't an error with TABLESLEUTH_CONFIG
        click.echo("   ⚠ No config file found (using defaults)")
        click.echo("     Run 'tablesleuth init' to create configuration files")

        if verbose:
            try:
                config = load_config()
                click.echo()
                click.echo("   Default values:")
                click.echo(f"     catalog.default: {config.catalog.default or '(not set)'}")
                click.echo(f"     gizmosql.uri: {config.gizmosql.uri}")
                click.echo(f"     gizmosql.username: {config.gizmosql.username}")
            except FileNotFoundError as e:
                click.echo(f"   ✗ Error loading defaults: {e}", err=True)
                all_checks_passed = False

    click.echo()

    # Check 2: Environment variable overrides
    click.echo("2. Environment Variable Overrides")
    click.echo("-" * 50)

    env_vars = {
        "TABLESLEUTH_CONFIG": "Config file path override",
        "TABLESLEUTH_CATALOG_NAME": "Default catalog override",
        "TABLESLEUTH_GIZMO_URI": "GizmoSQL URI override",
        "TABLESLEUTH_GIZMO_USERNAME": "GizmoSQL username override",
        "TABLESLEUTH_GIZMO_PASSWORD": "GizmoSQL password override",
        "PYICEBERG_HOME": "PyIceberg config directory",
    }

    env_vars_set = {k: v for k, v in env_vars.items() if os.getenv(k)}

    if env_vars_set:
        for var, desc in env_vars_set.items():
            value = os.getenv(var)
            if "PASSWORD" in var:
                value = "*" * len(value) if value else ""
            click.echo(f"   ✓ {var}={value}")
            if verbose:
                click.echo(f"     ({desc})")
    else:
        click.echo("   ⚠ No environment variables set")

    click.echo()

    # Check 3: PyIceberg configuration
    click.echo("3. PyIceberg Configuration (.pyiceberg.yaml)")
    click.echo("-" * 50)

    # Check for PyIceberg config file
    pyiceberg_paths = [
        Path.cwd() / ".pyiceberg.yaml",
        Path.home() / ".pyiceberg.yaml",
    ]

    # Check PYICEBERG_HOME override
    pyiceberg_home = os.getenv("PYICEBERG_HOME")
    if pyiceberg_home:
        pyiceberg_paths.insert(0, Path(pyiceberg_home) / ".pyiceberg.yaml")

    pyiceberg_found = None
    for path in pyiceberg_paths:
        if path.exists():
            pyiceberg_found = path
            break

    if pyiceberg_found:
        click.echo(f"   ✓ PyIceberg config found: {pyiceberg_found}")

        try:
            with pyiceberg_found.open() as f:
                pyiceberg_config = yaml.safe_load(f)

            click.echo("   ✓ Config file syntax valid")

            if verbose and pyiceberg_config and "catalog" in pyiceberg_config:
                catalogs = pyiceberg_config["catalog"]
                click.echo()
                click.echo(f"   Configured catalogs: {', '.join(catalogs.keys())}")
                for name, catalog_config in catalogs.items():
                    catalog_type = catalog_config.get("type", "unknown")
                    click.echo(f"     - {name} (type: {catalog_type})")
        except Exception as e:
            click.echo(f"   ✗ Config file error: {e}", err=True)
            all_checks_passed = False
    else:
        click.echo("   ⚠ No PyIceberg config found")
        click.echo("     Run 'tablesleuth init' to create configuration files")
        click.echo("     Required for Iceberg catalog access")

    click.echo()

    # Check 4: GizmoSQL connection (optional, only with flag)
    if with_gizmosql:
        click.echo("4. GizmoSQL Connection Test")
        click.echo("-" * 50)

        try:
            config = load_config()
            click.echo(f"   Testing connection to {config.gizmosql.uri}...")

            try:
                profiler = GizmoDuckDbProfiler(
                    uri=config.gizmosql.uri,
                    username=config.gizmosql.username,
                    password=config.gizmosql.password,
                    tls_skip_verify=config.gizmosql.tls_skip_verify,
                )
                # Try a simple query to verify connection works
                with profiler._connect() as conn, conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                click.echo("   ✓ GizmoSQL connection successful")
            except Exception as e:
                click.echo(f"   ✗ GizmoSQL connection failed: {e}", err=True)
                click.echo("     GizmoSQL is optional but required for:")
                click.echo("     - Column profiling")
                click.echo("     - Iceberg snapshot performance testing")
                click.echo("     See: docs/GIZMOSQL_DEPLOYMENT_GUIDE.md")
                all_checks_passed = False
        except Exception as e:
            click.echo(f"   ✗ Configuration error: {e}", err=True)
            all_checks_passed = False

        click.echo()
    else:
        click.echo("4. GizmoSQL Connection Test")
        click.echo("-" * 50)
        click.echo("   ⊘ Skipped (use --with-gizmosql to test)")
        click.echo("     GizmoSQL is optional but required for:")
        click.echo("     - Column profiling")
        click.echo("     - Iceberg snapshot performance testing")
        click.echo()

    click.echo("=" * 50)

    if all_checks_passed:
        click.echo("✓ All checks passed!")
        sys.exit(0)
    else:
        click.echo("⚠ Some checks failed or warnings present")
        click.echo()
        click.echo("To fix configuration issues:")
        click.echo("  1. Run 'tablesleuth init' to create config files")
        click.echo("  2. Edit configuration files as needed")
        click.echo("  3. Run 'tablesleuth config-check -v' for details")
        sys.exit(1)


def entry_point() -> None:
    """Entry point for the CLI."""
    main()


if __name__ == "__main__":
    entry_point()
