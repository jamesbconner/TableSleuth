"""Shared utilities for Delta Lake operations.

This module provides common functionality used by both DeltaAdapter and DeltaForensics
to avoid code duplication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyarrow import fs as pafs

try:
    from pyarrow import fs as pafs_module
except ImportError:
    pafs_module = None


def get_filesystem_and_path(
    table_uri: str, storage_options: dict[str, str] | None = None
) -> tuple[pafs.FileSystem | None, str]:
    """Get PyArrow filesystem and normalized path for a table URI.

    This is a shared utility function used by both DeltaAdapter and DeltaForensics
    to handle cloud URIs and local paths consistently.

    Args:
        table_uri: Table URI (local path or cloud URI like s3://bucket/path)
        storage_options: Optional cloud storage credentials and configuration

    Returns:
        Tuple of (filesystem, normalized_path)
        - filesystem: PyArrow filesystem for cloud storage, None for local
        - normalized_path: Normalized path component

    Raises:
        ImportError: If PyArrow is not installed for cloud storage
    """
    # Check if this is a cloud URI
    is_cloud = table_uri.startswith(("s3://", "gs://", "abfs://", "abfss://"))

    if is_cloud:
        # Cloud storage - create PyArrow filesystem
        if pafs_module is None:
            raise ImportError(
                "PyArrow is required for cloud storage support. Install with: pip install pyarrow"
            )

        # Create filesystem from URI and storage options
        filesystem, path = pafs_module.FileSystem.from_uri(table_uri)

        # Apply storage options if provided
        if storage_options:
            # Convert storage options to PyArrow format
            if table_uri.startswith("s3://"):
                # S3 filesystem
                s3_options = {}
                if "AWS_ACCESS_KEY_ID" in storage_options:
                    s3_options["access_key"] = storage_options["AWS_ACCESS_KEY_ID"]
                if "AWS_SECRET_ACCESS_KEY" in storage_options:
                    s3_options["secret_key"] = storage_options["AWS_SECRET_ACCESS_KEY"]
                if "AWS_REGION" in storage_options:
                    s3_options["region"] = storage_options["AWS_REGION"]
                if "AWS_ENDPOINT_URL" in storage_options:
                    s3_options["endpoint_override"] = storage_options["AWS_ENDPOINT_URL"]

                if s3_options:
                    filesystem = pafs_module.S3FileSystem(**s3_options)

        return filesystem, path
    else:
        # Local filesystem - handle file:// prefix
        original_uri = table_uri

        if table_uri.startswith("file:///"):
            table_uri = table_uri[8:]
        elif table_uri.startswith("file://"):
            table_uri = table_uri[7:]
            # macOS/Linux: Ensure absolute path has leading /
            # Only prepend / if it looks like an absolute path without the leading /
            # Don't prepend for relative paths (starting with .)
            if not table_uri.startswith(("/", "\\", ".")) and ":" not in table_uri:
                # This is likely a macOS/Linux absolute path missing the leading /
                # (e.g., "private/var/..." should be "/private/var/...")
                table_uri = "/" + table_uri
        elif table_uri.startswith("file:\\"):
            table_uri = table_uri[6:].lstrip("\\")

        # Additional check: If the original URI had file:// prefix and the path
        # doesn't start with / or \ or contain : (Windows drive), and it's not
        # a relative path (doesn't start with .), it's likely a
        # macOS absolute path missing the leading /
        # This handles cases where deltalake returns file://private/var/...
        if (
            original_uri.startswith("file://")
            and not table_uri.startswith(("/", "\\", "."))
            and ":" not in table_uri
            and "/" in table_uri
        ):  # Has path separators, so it's a path not just a name
            # This looks like an absolute Unix path missing the leading /
            table_uri = "/" + table_uri

        return None, table_uri
