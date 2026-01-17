"""Manager for local catalog snapshot table registration."""

from __future__ import annotations

import logging
from pathlib import Path

from pyiceberg.catalog import Catalog, load_catalog

from tablesleuth.exceptions import CatalogError, SnapshotRegistrationError

logger = logging.getLogger(__name__)


class SnapshotTestManager:
    """Manages local catalog snapshot table registration.

    Uses the local catalog configured in .pyiceberg.yaml to register
    snapshots as separate tables in a dedicated namespace for performance testing.
    """

    def __init__(self, catalog_name: str = "local"):
        """Initialize the snapshot test manager.

        Args:
            catalog_name: Name of catalog from .pyiceberg.yaml (default: 'local')
        """
        self._catalog_name = catalog_name
        self._catalog: Catalog | None = None
        self._registered_tables: set[str] = set()
        self._namespace = "snapshot_tests"

    def ensure_snapshot_namespace(self) -> str:
        """Ensure snapshot_tests namespace exists in local catalog.

        Returns:
            Namespace name

        Raises:
            CatalogError: If catalog cannot be loaded or namespace cannot be created
        """
        try:
            if self._catalog is None:
                # Load catalog from PyIceberg configuration
                try:
                    self._catalog = load_catalog(self._catalog_name)
                    logger.debug(f"Loaded catalog '{self._catalog_name}' from configuration")
                except Exception as e:
                    logger.exception(f"Failed to load catalog '{self._catalog_name}'")
                    raise CatalogError(
                        f"Failed to load catalog '{self._catalog_name}' from configuration. "
                        f"Ensure .pyiceberg.yaml is configured correctly: {e}"
                    ) from e

                # Create namespace if it doesn't exist
                try:
                    self._catalog.create_namespace(self._namespace)
                    logger.debug(
                        f"Created namespace '{self._namespace}' in catalog '{self._catalog_name}'"
                    )
                except Exception as e:
                    # Namespace might already exist, which is fine
                    logger.debug(f"Namespace '{self._namespace}' may already exist: {e}")

            return self._namespace
        except CatalogError:
            raise
        except Exception as e:
            logger.exception("Unexpected error ensuring snapshot namespace")
            raise CatalogError(f"Unexpected error ensuring snapshot namespace: {e}") from e

    def register_snapshot(
        self,
        source_metadata_path: str,
        snapshot_id: int,
        alias: str | None = None,
    ) -> str:
        """Register a snapshot as a table in snapshot_tests namespace.

        Args:
            source_metadata_path: Path to the source table's metadata file
            snapshot_id: Snapshot ID to register
            alias: Optional alias for the table name

        Returns:
            Full table identifier (snapshot_tests.table_name)

        Raises:
            SnapshotRegistrationError: If registration fails
        """
        if self._catalog is None:
            self.ensure_snapshot_namespace()

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
            # Note: PyIceberg's register_table() creates a new table entry
            # We need to use the metadata file that corresponds to this snapshot

            # For now, we'll use the source metadata path
            # In a full implementation, we'd need to find the specific metadata file
            # for this snapshot from the metadata log

            if self._catalog is None:
                raise CatalogError("Catalog not initialized")

            # Check if table already exists and drop it
            try:
                self._catalog.load_table(full_identifier)
                # If load_table succeeds, table exists - drop it
                logger.debug(f"Table {full_identifier} already exists, dropping it")
                self._catalog.drop_table(full_identifier)
            except Exception as e:
                # Table doesn't exist, which is fine
                # Common error messages: "not found", "does not exist", "doesn't exist", "not exist"
                error_msg = str(e).lower()
                if (
                    "not found" in error_msg
                    or "not exist" in error_msg
                    or "doesn't exist" in error_msg
                    or "does not exist" in error_msg
                ):
                    logger.debug(f"Table {full_identifier} does not exist yet: {e}")
                else:
                    # This is a real error (e.g., permission denied, connection issue)
                    logger.error(f"Failed to check/drop existing table {full_identifier}: {e}")
                    raise

            self._catalog.register_table(
                identifier=full_identifier,
                metadata_location=source_metadata_path,
            )

            self._registered_tables.add(full_identifier)
            logger.debug(f"Registered snapshot {snapshot_id} as {full_identifier}")

            return full_identifier

        except Exception as e:
            logger.error(f"Failed to register snapshot {snapshot_id}: {e}")
            raise SnapshotRegistrationError(f"Failed to register snapshot: {e}") from e

    def get_registered_tables(self) -> list[str]:
        """Get list of all registered snapshot tables in snapshot_tests namespace.

        Returns:
            List of table identifiers
        """
        return list(self._registered_tables)

    def cleanup_tables(self, table_names: list[str] | None = None) -> None:
        """Drop specified tables from snapshot_tests namespace or all tables if None.

        Args:
            table_names: Optional list of table names to drop. If None, drops all registered tables.
        """
        if self._catalog is None:
            logger.debug("No catalog to clean up")
            return

        tables_to_drop = table_names if table_names else list(self._registered_tables)

        for table_name in tables_to_drop:
            try:
                self._catalog.drop_table(table_name)
                self._registered_tables.discard(table_name)
                logger.debug(f"Dropped table {table_name} from snapshot_tests namespace")
            except Exception as e:
                logger.warning(f"Failed to drop table {table_name}: {e}")

    def get_catalog_path(self) -> str:
        """Get the path to the local catalog database file.

        Returns:
            Path to catalog database file

        Raises:
            CatalogError: If catalog is not initialized or path cannot be determined
        """
        if self._catalog is None:
            self.ensure_snapshot_namespace()

        # Try to extract the catalog path from the catalog properties
        # For SQLite catalogs, this is typically in the 'uri' property
        try:
            if self._catalog is not None and hasattr(self._catalog, "properties"):
                uri = self._catalog.properties.get("uri", "")
                if uri.startswith("sqlite:///"):
                    # Extract path from sqlite:///path/to/catalog.db
                    return str(uri.replace("sqlite:///", ""))

            # Fallback: try to get from catalog name in config
            # This requires reading .pyiceberg.yaml, which PyIceberg handles internally
            logger.warning("Could not determine catalog path from catalog properties")
            raise CatalogError(
                f"Could not determine catalog database path for catalog '{self._catalog_name}'"
            )
        except Exception as e:
            logger.exception("Failed to get catalog path")
            raise CatalogError(f"Failed to get catalog path: {e}") from e
