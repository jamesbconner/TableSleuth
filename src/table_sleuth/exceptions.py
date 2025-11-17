"""Custom exceptions for Table Sleuth."""

from __future__ import annotations


class TableSleuthError(Exception):
    """Base exception for all Table Sleuth errors."""

    pass


class IcebergError(TableSleuthError):
    """Base exception for Iceberg-related errors."""

    pass


class TableLoadError(IcebergError):
    """Error loading Iceberg table.

    Raised when:
    - Metadata file cannot be found or read
    - Catalog cannot be loaded
    - Table identifier is invalid
    - Unsupported Iceberg format version
    """

    pass


class CatalogError(IcebergError):
    """Error with test catalog operations.

    Raised when:
    - Cannot create test catalog
    - Cannot write to catalog location
    - Catalog database is corrupted
    - Catalog file is in use
    """

    pass


class SnapshotRegistrationError(IcebergError):
    """Error registering snapshot as table.

    Raised when:
    - Invalid snapshot ID
    - Metadata file not accessible
    - Catalog write failure
    - Table already exists with same name
    """

    pass


class QueryExecutionError(IcebergError):
    """Error executing query.

    Raised when:
    - Invalid SQL syntax
    - Table not found in catalog
    - GizmoSQL connection failure
    - Query timeout
    - Insufficient permissions
    """

    pass


class SnapshotNotFoundError(IcebergError):
    """Error when snapshot cannot be found.

    Raised when:
    - Snapshot ID does not exist in table
    - Snapshot has been expired/deleted
    """

    pass


class MetadataError(IcebergError):
    """Error reading or parsing Iceberg metadata.

    Raised when:
    - Metadata file is corrupted
    - Metadata format is invalid
    - Required metadata fields are missing
    """

    pass
