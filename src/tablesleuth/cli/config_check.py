"""Check TableSleuth configuration and validate settings."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
import yaml

from tablesleuth.config import get_config_file_path, load_config
from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler


@click.command("config-check")
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
