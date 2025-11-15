from __future__ import annotations

import sys
from typing import Optional

import click

from .config import load_config
from .services.formats.iceberg import IcebergAdapter
from .tui.app import TableSleuthApp


@click.group()
def main() -> None:
    """Table Sleuth command line interface."""


@main.command("tui")
@click.argument("identifier", type=str)
@click.option(
    "--catalog",
    "catalog_name",
    type=str,
    default=None,
    help="Catalog name (for example local). If omitted, identifier is treated as a path.",
)
def run_tui(identifier: str, catalog_name: Optional[str]) -> None:
    """Launch the Textual TUI against a table."""
    config = load_config()
    adapter = IcebergAdapter(default_catalog=config.catalog.default)

    try:
        table = adapter.open_table(identifier, catalog_name or config.catalog.default)
    except Exception as exc:  # refine later
        click.echo(f"Failed to open table {identifier}: {exc}", err=True)
        sys.exit(1)

    app = TableSleuthApp(table_handle=table, adapter=adapter, config=config)
    app.run()


def entry_point() -> None:
    main()


if __name__ == "__main__":
    entry_point()
