"""Initialize TableSleuth configuration files."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from tablesleuth.utils.config_templates import get_pyiceberg_template, get_tablesleuth_template


@click.command("init")
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing configuration files.",
)
def init(force: bool) -> None:
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
