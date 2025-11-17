"""Manager for test catalog and snapshot table registration."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from pyiceberg.catalog.sql import SqlCatalog

from table_sleuth.exceptions import CatalogError, SnapshotRegistrationError

logger = logging.getLogger(__name__)


class SnapshotTestManager:
    """Manages test catalog and snapshot table registration.

    Creates a temporary SQLite-based Iceberg catalog for registering
    snapshots as separate tables for performance testing.
    """

    def __init__(self, test_catalog_path: str | None = None):
        """Initialize the snapshot test manager.

        Args:
            test_catalog_path: Optional path for test catalog. If None, uses temp directory.
        """
        self._test_catalog_path = test_catalog_path
        self._catalog: SqlCatalog | None = None
        self._registered_tables: list[str] = []
        self._namespace = "snapshot_tests"

    def ensure_test_catalog(self) -> str:
        """Create test catalog if it doesn't exist.

        Returns:
            Path to the catalog database file

        Raises:
            CatalogError: If catalog cannot be created
        """
        try:
            if self._test_catalog_path is None:
                # Create in temp directory
                temp_dir = tempfile.gettempdir()
                self._test_catalog_path = str(Path(temp_dir) / "table_sleuth_test_catalog.db")

            if self._catalog is None:
                # Create SQLite catalog
                try:
                    self._catalog = SqlCatalog(
                        "test_catalog",
                        **{
                            "uri": f"sqlite:///{self._test_catalog_path}",
                            "warehouse": str(Path(self._test_catalog_path).parent / "warehouse"),
                        },
                    )
                except Exception as e:
                    logger.exception("Failed to create test catalog")
                    raise CatalogError(f"Failed to create test catalog: {e}") from e

                # Create namespace if it doesn't exist
                try:
                    self._catalog.create_namespace(self._namespace)
                    logger.info(f"Created namespace {self._namespace} in test catalog")
                except Exception as e:
                    # Namespace might already exist
                    logger.debug(f"Namespace creation skipped: {e}")

            return self._test_catalog_path
        except CatalogError:
            raise
        except Exception as e:
            logger.exception("Unexpected error ensuring test catalog")
            raise CatalogError(f"Unexpected error ensuring test catalog: {e}") from e

    def register_snapshot(
        self,
        source_metadata_path: str,
        snapshot_id: int,
        alias: str | None = None,
    ) -> str:
        """Register a snapshot as a table.

        Args:
            source_metadata_path: Path to the source table's metadata file
            snapshot_id: Snapshot ID to register
            alias: Optional alias for the table name

        Returns:
            Full table identifier (namespace.table_name)

        Raises:
            RuntimeError: If catalog not initialized or registration fails
        """
        if self._catalog is None:
            self.ensure_test_catalog()

        # Generate table name
        if alias:
            table_name = alias
        else:
            # Extract source table name from metadata path
            source_name = Path(source_metadata_path).parent.parent.name
            table_name = f"{source_name}_snap_{snapshot_id}"

        full_identifier = f"{self._namespace}.{table_name}"

        try:
            # Register table by creating a catalog entry pointing to the snapshot
            # Note: PyIceberg's SqlCatalog.register_table() creates a new table entry
            # We need to use the metadata file that corresponds to this snapshot

            # For now, we'll use the source metadata path
            # In a full implementation, we'd need to find the specific metadata file
            # for this snapshot from the metadata log

            if self._catalog is None:
                raise CatalogError("Catalog not initialized")

            self._catalog.register_table(
                identifier=full_identifier,
                metadata_location=source_metadata_path,
            )

            self._registered_tables.append(full_identifier)
            logger.info(f"Registered snapshot {snapshot_id} as {full_identifier}")

            return full_identifier

        except Exception as e:
            logger.error(f"Failed to register snapshot {snapshot_id}: {e}")
            raise RuntimeError(f"Failed to register snapshot: {e}") from e

    def get_registered_tables(self) -> list[str]:
        """Get list of all registered snapshot tables.

        Returns:
            List of table identifiers
        """
        return self._registered_tables.copy()

    def cleanup_tables(self, table_names: list[str] | None = None):
        """Drop specified tables or all tables if None.

        Args:
            table_names: Optional list of table names to drop. If None, drops all.
        """
        if self._catalog is None:
            logger.debug("No catalog to clean up")
            return

        tables_to_drop = table_names if table_names else self._registered_tables.copy()

        for table_name in tables_to_drop:
            try:
                self._catalog.drop_table(table_name)
                if table_name in self._registered_tables:
                    self._registered_tables.remove(table_name)
                logger.info(f"Dropped table {table_name}")
            except Exception as e:
                logger.warning(f"Failed to drop table {table_name}: {e}")

    def cleanup_catalog(self):
        """Delete the test catalog entirely.

        Drops all tables and deletes the catalog database file.
        """
        # Drop all tables first
        self.cleanup_tables()

        # Close catalog connection
        if self._catalog is not None:
            self._catalog = None

        # Delete catalog file
        if self._test_catalog_path and Path(self._test_catalog_path).exists():
            try:
                Path(self._test_catalog_path).unlink()
                logger.info(f"Deleted test catalog at {self._test_catalog_path}")
            except Exception as e:
                logger.warning(f"Failed to delete catalog file: {e}")

        # Reset state
        self._test_catalog_path = None
        self._registered_tables.clear()

    def get_catalog_path(self) -> str | None:
        """Get the path to the test catalog database.

        Returns:
            Path to catalog database, or None if not created
        """
        return self._test_catalog_path
