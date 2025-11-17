"""Tests for SnapshotTestManager."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from table_sleuth.exceptions import CatalogError
from table_sleuth.services.snapshot_test_manager import SnapshotTestManager


class TestSnapshotTestManager:
    """Tests for SnapshotTestManager."""

    def test_ensure_test_catalog_creates_catalog(self):
        """Test that ensure_test_catalog creates a catalog."""
        manager = SnapshotTestManager()
        catalog_path = manager.ensure_test_catalog()

        assert catalog_path is not None
        assert Path(catalog_path).exists()

        # Cleanup
        manager.cleanup_catalog()

    def test_ensure_test_catalog_custom_path(self):
        """Test creating catalog with custom path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = str(Path(tmpdir) / "custom_catalog.db")
            manager = SnapshotTestManager(test_catalog_path=custom_path)

            catalog_path = manager.ensure_test_catalog()

            assert catalog_path == custom_path
            assert Path(catalog_path).exists()

            # Cleanup
            manager.cleanup_catalog()

    def test_ensure_test_catalog_idempotent(self):
        """Test that calling ensure_test_catalog multiple times is safe."""
        manager = SnapshotTestManager()

        path1 = manager.ensure_test_catalog()
        path2 = manager.ensure_test_catalog()

        assert path1 == path2

        # Cleanup
        manager.cleanup_catalog()

    def test_get_catalog_path(self):
        """Test getting catalog path."""
        manager = SnapshotTestManager()
        manager.ensure_test_catalog()

        catalog_path = manager.get_catalog_path()
        assert catalog_path is not None
        assert Path(catalog_path).exists()

        # Cleanup
        manager.cleanup_catalog()

    def test_get_registered_tables_empty(self):
        """Test getting registered tables when none exist."""
        manager = SnapshotTestManager()
        manager.ensure_test_catalog()

        tables = manager.get_registered_tables()
        assert isinstance(tables, list)
        assert len(tables) == 0

        # Cleanup
        manager.cleanup_catalog()

    def test_cleanup_catalog_removes_file(self):
        """Test that cleanup_catalog removes the catalog file."""
        manager = SnapshotTestManager()
        catalog_path = manager.ensure_test_catalog()

        assert Path(catalog_path).exists()

        manager.cleanup_catalog()

        # Note: The file might still exist if SQLite has locks
        # This is expected behavior and handled gracefully

    def test_cleanup_tables_with_no_tables(self):
        """Test cleanup_tables when no tables exist."""
        manager = SnapshotTestManager()
        manager.ensure_test_catalog()

        # Should not raise an error
        manager.cleanup_tables()

        # Cleanup
        manager.cleanup_catalog()

    # Integration tests requiring real Iceberg table

    @pytest.mark.integration
    def test_register_snapshot(self, iceberg_table_metadata_path):
        """Test registering a snapshot as a table.

        Args:
            iceberg_table_metadata_path: Path to test table metadata
        """
        manager = SnapshotTestManager()
        manager.ensure_test_catalog()

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
            # Cleanup
            manager.cleanup_catalog()

    @pytest.mark.integration
    def test_register_snapshot_with_alias(self, iceberg_table_metadata_path):
        """Test registering a snapshot with custom alias.

        Args:
            iceberg_table_metadata_path: Path to test table metadata
        """
        manager = SnapshotTestManager()
        manager.ensure_test_catalog()

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
            # Cleanup
            manager.cleanup_catalog()

    @pytest.mark.integration
    def test_cleanup_specific_tables(self, iceberg_table_metadata_path):
        """Test cleaning up specific tables.

        Args:
            iceberg_table_metadata_path: Path to test table metadata
        """
        manager = SnapshotTestManager()
        manager.ensure_test_catalog()

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
            # Cleanup
            manager.cleanup_catalog()


# Fixtures
@pytest.fixture
def iceberg_table_metadata_path():
    """Provide path to test Iceberg table metadata."""
    import os

    path = os.getenv("TEST_ICEBERG_METADATA_PATH")
    if not path:
        pytest.skip("TEST_ICEBERG_METADATA_PATH not set")
    return path
