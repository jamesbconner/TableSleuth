"""Tests for VersionSchemaView widget."""

from __future__ import annotations

import pytest
from textual.app import App
from textual.widgets import DataTable

from tablesleuth.tui.views.delta_view import VersionSchemaView


class SchemaViewTestApp(App):
    """Test app for mounting VersionSchemaView."""

    def compose(self):
        """Compose the test app."""
        yield VersionSchemaView(id="schema-view")


@pytest.mark.asyncio
async def test_schema_view_populates_on_first_mount() -> None:
    """Test that schema view populates table on first mount.

    Regression test for bug where optimization check prevented
    table population when on_mount() called update_schema(self._schema)
    with the same object reference.
    """
    # Create schema
    schema = {"id": "bigint", "name": "string", "created_at": "timestamp"}

    app = SchemaViewTestApp()

    async with app.run_test() as pilot:
        # Get the view
        view = app.query_one("#schema-view", VersionSchemaView)

        # Manually set _schema (simulating what happens in the parent view)
        view._schema = schema

        # Call on_mount manually to simulate remounting
        view.on_mount()

        await pilot.pause()

        # Get the table
        table = view.query_one("#schema-table", DataTable)

        # Verify table is populated
        assert table.row_count == 3, "Table should have 3 rows"


@pytest.mark.asyncio
async def test_schema_view_skips_update_when_unchanged() -> None:
    """Test that schema view skips update when schema unchanged and table populated."""
    # Create schema
    schema = {"id": "bigint", "name": "string"}

    app = SchemaViewTestApp()

    async with app.run_test() as pilot:
        # Get the view
        view = app.query_one("#schema-view", VersionSchemaView)

        # Update with schema
        view.update_schema(schema)

        await pilot.pause()

        # Get the table
        table = view.query_one("#schema-table", DataTable)

        # Verify initial population
        assert table.row_count == 2

        # Call update_schema with same schema (should skip)
        view.update_schema(schema)

        # Table should still have same content
        assert table.row_count == 2


@pytest.mark.asyncio
async def test_schema_view_updates_when_schema_changes() -> None:
    """Test that schema view updates when schema actually changes."""
    # Create initial schema
    schema1 = {"id": "bigint", "name": "string"}

    app = SchemaViewTestApp()

    async with app.run_test() as pilot:
        # Get the view
        view = app.query_one("#schema-view", VersionSchemaView)

        # Update with initial schema
        view.update_schema(schema1)

        await pilot.pause()

        # Get the table
        table = view.query_one("#schema-table", DataTable)

        # Verify initial population
        assert table.row_count == 2

        # Update with different schema
        schema2 = {"id": "bigint", "name": "string", "email": "string"}
        view.update_schema(schema2)

        # Table should have new content
        assert table.row_count == 3


@pytest.mark.asyncio
async def test_schema_view_clear() -> None:
    """Test that schema view clears correctly."""
    # Create schema
    schema = {"id": "bigint", "name": "string"}

    app = SchemaViewTestApp()

    async with app.run_test() as pilot:
        # Get the view
        view = app.query_one("#schema-view", VersionSchemaView)

        # Update with schema
        view.update_schema(schema)

        await pilot.pause()

        # Get the table
        table = view.query_one("#schema-table", DataTable)

        # Verify initial population
        assert table.row_count == 2

        # Clear the view
        view.clear()

        # Table should be empty
        assert table.row_count == 0
        assert view._schema is None
