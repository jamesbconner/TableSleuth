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
        click.echo(_suggest_init_on_config_error(""), err=True)
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
            if path.exists() and force:
                # Backup existing file
                backup_path = path.with_suffix(path.suffix + ".backup")
                path.rename(backup_path)
                click.echo(f"  Backed up existing {name} to {backup_path.name}")

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
def config_check(verbose: bool) -> None:
    """Check TableSleuth configuration and validate settings.

    Validates configuration files and tests connections to verify setup.
    Shows which configuration files are being used and reports any issues.

    Checks performed:
    - Configuration file locations and syntax
    - Environment variable overrides
    - GizmoSQL connection (if configured)
    - PyIceberg catalog configuration

    Examples:

    \b
    # Quick check (pass/fail)
    tablesleuth config-check

    \b
    # Detailed check with all values
    tablesleuth config-check --verbose
    """
    click.echo("TableSleuth Configuration Check")
    click.echo("=" * 50)
    click.echo()

    all_checks_passed = True

    # Check 1: TableSleuth configuration file
    click.echo("1. TableSleuth Configuration (tablesleuth.toml)")
    click.echo("-" * 50)

    config_path = get_config_file_path()
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
    else:
        click.echo("   ⚠ No config file found (using defaults)")
        click.echo("     Run 'tablesleuth init' to create configuration files")

        if verbose:
            config = load_config()
            click.echo()
            click.echo("   Default values:")
            click.echo(f"     catalog.default: {config.catalog.default or '(not set)'}")
            click.echo(f"     gizmosql.uri: {config.gizmosql.uri}")
            click.echo(f"     gizmosql.username: {config.gizmosql.username}")

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

    # Check 4: GizmoSQL connection
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
