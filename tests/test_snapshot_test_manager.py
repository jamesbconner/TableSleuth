"""Tests for SnapshotTestManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tablesleuth.exceptions import CatalogError
from tablesleuth.services.snapshot_test_manager import SnapshotTestManager


class TestSnapshotTestManager:
    """Tests for SnapshotTestManager."""

    @patch("tablesleuth.services.snapshot_test_manager.load_catalog")
    def test_ensure_snapshot_namespace_loads_catalog(self, mock_load_catalog):
        """Test that ensure_snapshot_namespace loads the catalog from config."""
        mock_catalog = MagicMock()
        mock_load_catalog.return_value = mock_catalog

        manager = SnapshotTestManager(catalog_name="local")
        namespace = manager.ensure_snapshot_namespace()

        assert namespace == "snapshot_tests"
        mock_load_catalog.assert_called_once_with("local")
        mock_catalog.create_namespace.assert_called_once_with("snapshot_tests")

    @patch("tablesleuth.services.snapshot_test_manager.load_catalog")
    def test_ensure_snapshot_namespace_handles_existing_namespace(self, mock_load_catalog):
        """Test that ensure_snapshot_namespace handles existing namespace gracefully."""
        mock_catalog = MagicMock()
        mock_catalog.create_namespace.side_effect = Exception("Namespace already exists")
        mock_load_catalog.return_value = mock_catalog

        manager = SnapshotTestManager(catalog_name="local")
        namespace = manager.ensure_snapshot_namespace()

        # Should not raise, just log
        assert namespace == "snapshot_tests"

    @patch("tablesleuth.services.snapshot_test_manager.load_catalog")
    def test_ensure_snapshot_namespace_idempotent(self, mock_load_catalog):
        """Test that calling ensure_snapshot_namespace multiple times is safe."""
        mock_catalog = MagicMock()
        mock_load_catalog.return_value = mock_catalog

        manager = SnapshotTestManager(catalog_name="local")

        namespace1 = manager.ensure_snapshot_namespace()
        namespace2 = manager.ensure_snapshot_namespace()

        assert namespace1 == namespace2
        # Should only load catalog once
        assert mock_load_catalog.call_count == 1

    @patch("tablesleuth.services.snapshot_test_manager.load_catalog")
    def test_get_catalog_path_from_sqlite_uri(self, mock_load_catalog):
        """Test getting catalog path from SQLite URI."""
        mock_catalog = MagicMock()
        mock_catalog.properties = {"uri": "sqlite:////path/to/catalog.db"}
        mock_load_catalog.return_value = mock_catalog

        manager = SnapshotTestManager(catalog_name="local")
        catalog_path = manager.get_catalog_path()

        assert catalog_path == "/path/to/catalog.db"

    @patch("tablesleuth.services.snapshot_test_manager.load_catalog")
    def test_get_catalog_path_raises_on_missing_uri(self, mock_load_catalog):
        """Test that get_catalog_path raises error when URI is not available."""
        mock_catalog = MagicMock()
        mock_catalog.properties = {}
        mock_load_catalog.return_value = mock_catalog

        manager = SnapshotTestManager(catalog_name="local")

        with pytest.raises(CatalogError, match="Could not determine catalog database path"):
            manager.get_catalog_path()

    @patch("tablesleuth.services.snapshot_test_manager.load_catalog")
    def test_get_registered_tables_empty(self, mock_load_catalog):
        """Test getting registered tables when none exist."""
        mock_catalog = MagicMock()
        mock_load_catalog.return_value = mock_catalog

        manager = SnapshotTestManager(catalog_name="local")
        manager.ensure_snapshot_namespace()

        tables = manager.get_registered_tables()
        assert isinstance(tables, list)
        assert len(tables) == 0

    @patch("tablesleuth.services.snapshot_test_manager.load_catalog")
    def test_cleanup_tables_with_no_tables(self, mock_load_catalog):
        """Test cleanup_tables when no tables exist."""
        mock_catalog = MagicMock()
        mock_load_catalog.return_value = mock_catalog

        manager = SnapshotTestManager(catalog_name="local")
        manager.ensure_snapshot_namespace()

        # Should not raise an error
        manager.cleanup_tables()

    @patch("tablesleuth.services.snapshot_test_manager.load_catalog")
    def test_cleanup_tables_drops_registered_tables(self, mock_load_catalog):
        """Test that cleanup_tables drops all registered tables."""
        mock_catalog = MagicMock()
        mock_load_catalog.return_value = mock_catalog

        manager = SnapshotTestManager(catalog_name="local")
        manager.ensure_snapshot_namespace()

        # Simulate registered tables
        manager._registered_tables = {"snapshot_tests.table1", "snapshot_tests.table2"}

        manager.cleanup_tables()

        # Should drop both tables
        assert mock_catalog.drop_table.call_count == 2
        assert len(manager._registered_tables) == 0

    @patch("tablesleuth.services.snapshot_test_manager.load_catalog")
    def test_register_snapshot_prevents_duplicates(self, mock_load_catalog):
        """Test that registering the same snapshot multiple times doesn't create duplicates.

        This verifies the fix for the duplicate registration bug where re-registering
        a snapshot (e.g., by toggling compare mode) would add duplicate entries.
        """
        mock_catalog = MagicMock()
        mock_catalog.load_table.side_effect = Exception("Table doesn't exist")
        mock_load_catalog.return_value = mock_catalog

        manager = SnapshotTestManager(catalog_name="local")
        manager.ensure_snapshot_namespace()

        # Register the same snapshot twice
        metadata_path = "/path/to/metadata/v1.metadata.json"
        table1 = manager.register_snapshot(metadata_path, snapshot_id=123)
        table2 = manager.register_snapshot(metadata_path, snapshot_id=123)

        # Both should return the same identifier
        assert table1 == table2

        # Should only have one entry in registered tables
        registered = manager.get_registered_tables()
        assert len(registered) == 1
        assert table1 in registered

        # Cleanup should only try to drop once
        manager.cleanup_tables()
        assert mock_catalog.drop_table.call_count == 1

    # Integration tests requiring real Iceberg table and configured local catalog

    @pytest.mark.integration
    def test_register_snapshot(self, iceberg_table_metadata_path):
        """Test registering a snapshot as a table.

        Note: Requires .pyiceberg.yaml with 'local' catalog configured.

        Args:
            iceberg_table_metadata_path: Path to test table metadata
        """
        manager = SnapshotTestManager(catalog_name="local")
        manager.ensure_snapshot_namespace()

        try:
            # Register snapshot
            table_name = manager.register_snapshot(
                source_metadata_path=iceberg_table_metadata_path,
                snapshot_id=1,  # Assuming snapshot 1 exists
            )

            assert table_name is not None
            assert "snapshot_tests" in table_name
            assert "snap_1" in table_name

            # Verify it's in registered tables
            tables = manager.get_registered_tables()
            assert table_name in tables

        finally:
            # Cleanup only the registered tables, not the catalog
            manager.cleanup_tables()

    @pytest.mark.integration
    def test_register_snapshot_with_alias(self, iceberg_table_metadata_path):
        """Test registering a snapshot with custom alias.

        Note: Requires .pyiceberg.yaml with 'local' catalog configured.

        Args:
            iceberg_table_metadata_path: Path to test table metadata
        """
        manager = SnapshotTestManager(catalog_name="local")
        manager.ensure_snapshot_namespace()

        try:
            # Register with alias
            table_name = manager.register_snapshot(
                source_metadata_path=iceberg_table_metadata_path,
                snapshot_id=1,
                alias="test_snapshot",
            )

            assert table_name is not None
            assert "test_snapshot" in table_name

        finally:
            # Cleanup only the registered tables
            manager.cleanup_tables()

    @pytest.mark.integration
    def test_cleanup_specific_tables(self, iceberg_table_metadata_path):
        """Test cleaning up specific tables.

        Note: Requires .pyiceberg.yaml with 'local' catalog configured.

        Args:
            iceberg_table_metadata_path: Path to test table metadata
        """
        manager = SnapshotTestManager(catalog_name="local")
        manager.ensure_snapshot_namespace()

        try:
            # Register two snapshots
            table1 = manager.register_snapshot(
                source_metadata_path=iceberg_table_metadata_path,
                snapshot_id=1,
            )
            table2 = manager.register_snapshot(
                source_metadata_path=iceberg_table_metadata_path,
                snapshot_id=2,
            )

            # Cleanup only table1
            manager.cleanup_tables([table1])

            # Verify table1 is gone but table2 remains
            tables = manager.get_registered_tables()
            assert table1 not in tables
            assert table2 in tables

        finally:
            # Cleanup all registered tables
            manager.cleanup_tables()


# Fixtures
@pytest.fixture
def iceberg_table_metadata_path():
    """Provide path to test Iceberg table metadata."""
    import os

    path = os.getenv("TEST_ICEBERG_METADATA_PATH")
    if not path:
        pytest.skip("TEST_ICEBERG_METADATA_PATH not set")
    return path
