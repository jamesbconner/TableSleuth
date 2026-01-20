"""Path utilities for handling local and cloud storage paths.

This module provides utilities for working with paths across different storage systems
including local filesystem, S3, GCS, Azure Blob Storage, and others.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

# Cloud storage URI schemes supported by PyArrow and PyIceberg
S3_SCHEMES = ("s3://", "s3a://", "s3n://")
GCS_SCHEMES = ("gs://", "gcs://")
AZURE_SCHEMES = ("abfs://", "abfss://", "wasb://", "wasbs://")
HDFS_SCHEMES = ("hdfs://", "viewfs://")

# All cloud storage schemes
CLOUD_SCHEMES = S3_SCHEMES + GCS_SCHEMES + AZURE_SCHEMES + HDFS_SCHEMES

StorageType = Literal["local", "s3", "gcs", "azure", "hdfs", "unknown"]


def is_cloud_path(path: str) -> bool:
    """Check if path is a cloud storage path.

    Supports S3, GCS, Azure Blob Storage, and HDFS schemes.

    Args:
        path: Path to check

    Returns:
        True if path uses a cloud storage scheme

    Examples:
        >>> is_cloud_path("s3://bucket/file.parquet")
        True
        >>> is_cloud_path("s3a://bucket/file.parquet")
        True
        >>> is_cloud_path("/local/path/file.parquet")
        False
    """
    path_str = str(path).lower()
    return any(path_str.startswith(scheme) for scheme in CLOUD_SCHEMES)


def is_s3_path(path: str) -> bool:
    """Check if path is an S3 path.

    Supports s3://, s3a://, and s3n:// schemes.

    Args:
        path: Path to check

    Returns:
        True if path uses an S3 scheme

    Examples:
        >>> is_s3_path("s3://bucket/file.parquet")
        True
        >>> is_s3_path("s3a://bucket/file.parquet")
        True
        >>> is_s3_path("gs://bucket/file.parquet")
        False
    """
    path_str = str(path).lower()
    return any(path_str.startswith(scheme) for scheme in S3_SCHEMES)


def is_gcs_path(path: str) -> bool:
    """Check if path is a GCS path.

    Supports gs:// and gcs:// schemes.

    Args:
        path: Path to check

    Returns:
        True if path uses a GCS scheme
    """
    path_str = str(path).lower()
    return any(path_str.startswith(scheme) for scheme in GCS_SCHEMES)


def is_azure_path(path: str) -> bool:
    """Check if path is an Azure Blob Storage path.

    Supports abfs://, abfss://, wasb://, and wasbs:// schemes.

    Args:
        path: Path to check

    Returns:
        True if path uses an Azure scheme
    """
    path_str = str(path).lower()
    return any(path_str.startswith(scheme) for scheme in AZURE_SCHEMES)


def is_hdfs_path(path: str) -> bool:
    """Check if path is an HDFS path.

    Supports hdfs:// and viewfs:// schemes.

    Args:
        path: Path to check

    Returns:
        True if path uses an HDFS scheme
    """
    path_str = str(path).lower()
    return any(path_str.startswith(scheme) for scheme in HDFS_SCHEMES)


def get_storage_type(path: str) -> StorageType:
    """Determine the storage type for a given path.

    Args:
        path: Path to analyze

    Returns:
        Storage type: "local", "s3", "gcs", "azure", "hdfs", or "unknown"

    Examples:
        >>> get_storage_type("s3://bucket/file.parquet")
        's3'
        >>> get_storage_type("/local/path/file.parquet")
        'local'
    """
    if is_s3_path(path):
        return "s3"
    elif is_gcs_path(path):
        return "gcs"
    elif is_azure_path(path):
        return "azure"
    elif is_hdfs_path(path):
        return "hdfs"
    elif not any(str(path).lower().startswith(scheme) for scheme in CLOUD_SCHEMES):
        return "local"
    else:
        return "unknown"


def is_local_path(path: str) -> bool:
    """Check if path is a local filesystem path.

    Args:
        path: Path to check

    Returns:
        True if path is a local filesystem path (not cloud storage)

    Examples:
        >>> is_local_path("/local/path/file.parquet")
        True
        >>> is_local_path("s3://bucket/file.parquet")
        False
    """
    return get_storage_type(path) == "local"


def should_check_local_exists(path: str) -> bool:
    """Determine if a path should be checked using local filesystem exists().

    This is a helper for code that needs to validate paths before passing them
    to libraries that handle cloud storage (like PyIceberg, PyArrow).

    Args:
        path: Path to check

    Returns:
        True if path should be validated using Path.exists(), False if it should
        be passed directly to cloud-aware libraries

    Examples:
        >>> should_check_local_exists("/local/path/file.parquet")
        True
        >>> should_check_local_exists("s3://bucket/file.parquet")
        False

    Note:
        Cloud storage paths should be validated by the libraries that handle them
        (PyIceberg, PyArrow) rather than using local filesystem checks.
    """
    return is_local_path(path)


def validate_local_path_exists(path: str) -> bool:
    """Validate that a local path exists.

    Only checks local filesystem paths. Cloud storage paths are not validated
    and will return True (they should be validated by cloud-aware libraries).

    Args:
        path: Path to validate

    Returns:
        True if path exists (for local paths) or is a cloud path

    Raises:
        FileNotFoundError: If local path does not exist

    Examples:
        >>> validate_local_path_exists("/existing/file.parquet")
        True
        >>> validate_local_path_exists("s3://bucket/file.parquet")
        True
        >>> validate_local_path_exists("/nonexistent/file.parquet")
        Traceback (most recent call last):
        ...
        FileNotFoundError: Path not found: /nonexistent/file.parquet
    """
    if should_check_local_exists(path):
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Path not found: {path}")
    # Cloud paths are assumed valid - let the cloud library validate them
    return True


def normalize_s3_scheme(path: str) -> str:
    """Normalize S3 path to use s3:// scheme.

    Converts s3a:// and s3n:// to s3:// for consistency.
    Case-insensitive matching.

    Args:
        path: S3 path with any S3 scheme

    Returns:
        Path with s3:// scheme

    Examples:
        >>> normalize_s3_scheme("s3a://bucket/file.parquet")
        's3://bucket/file.parquet'
        >>> normalize_s3_scheme("s3n://bucket/file.parquet")
        's3://bucket/file.parquet'
        >>> normalize_s3_scheme("s3://bucket/file.parquet")
        's3://bucket/file.parquet'
        >>> normalize_s3_scheme("S3A://bucket/file.parquet")
        's3://bucket/file.parquet'
    """
    path_lower = path.lower()
    if path_lower.startswith("s3a://"):
        return "s3://" + path[6:]
    elif path_lower.startswith("s3n://"):
        return "s3://" + path[6:]
    elif path_lower.startswith("s3://"):
        # Normalize to lowercase scheme
        return "s3://" + path[5:]
    return path


def strip_scheme(path: str) -> str:
    """Strip the URI scheme from a path.

    Removes s3://, s3a://, gs://, etc. prefixes from paths.
    Case-insensitive matching.

    Args:
        path: Path with or without scheme

    Returns:
        Path without scheme prefix

    Examples:
        >>> strip_scheme("s3://bucket/path/file.parquet")
        'bucket/path/file.parquet'
        >>> strip_scheme("s3a://bucket/path/file.parquet")
        'bucket/path/file.parquet'
        >>> strip_scheme("S3://bucket/path/file.parquet")
        'bucket/path/file.parquet'
        >>> strip_scheme("/local/path/file.parquet")
        '/local/path/file.parquet'
    """
    path_str = str(path)
    path_lower = path_str.lower()
    for scheme in CLOUD_SCHEMES:
        if path_lower.startswith(scheme):
            return path_str[len(scheme) :]
    return path_str
