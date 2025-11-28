"""Filesystem abstraction for local and S3 file access."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import BinaryIO, Union

import pyarrow.fs as pafs

logger = logging.getLogger(__name__)


class FileSystem:
    """Unified filesystem interface for local and S3 files."""

    def __init__(self, region: str | None = None):
        """Initialize filesystem with S3 support.

        Args:
            region: AWS region for S3 access. If None, uses AWS_REGION or AWS_DEFAULT_REGION
                   environment variable, or defaults to "us-east-2"
        """
        if region is None:
            region = (
                os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-2"
            )

        self._region = region
        self._s3_fs = pafs.S3FileSystem(region=region)
        self._local_fs = pafs.LocalFileSystem()

    @property
    def region(self) -> str:
        """Get the configured AWS region."""
        return self._region

    def is_s3_path(self, path: str) -> bool:
        """Check if path is an S3 path.

        Args:
            path: File path to check

        Returns:
            True if path starts with s3://
        """
        return str(path).startswith("s3://")

    def normalize_s3_path(self, path: str) -> str:
        """Remove s3:// prefix for PyArrow filesystem.

        Args:
            path: S3 path with s3:// prefix

        Returns:
            Path without s3:// prefix
        """
        if self.is_s3_path(path):
            return path[5:]  # Remove "s3://"
        return path

    def exists(self, path: str) -> bool:
        """Check if file exists.

        Args:
            path: Local or S3 path

        Returns:
            True if file exists
        """
        try:
            if self.is_s3_path(path):
                normalized = self.normalize_s3_path(path)
                file_info = self._s3_fs.get_file_info(normalized)
                return file_info.type != pafs.FileType.NotFound
            else:
                return Path(path).exists()
        except Exception as e:
            logger.debug(f"Error checking if file exists {path}: {e}")
            return False

    def get_size(self, path: str) -> int:
        """Get file size in bytes.

        Args:
            path: Local or S3 path

        Returns:
            File size in bytes
        """
        if self.is_s3_path(path):
            normalized = self.normalize_s3_path(path)
            file_info = self._s3_fs.get_file_info(normalized)
            return file_info.size
        else:
            return Path(path).stat().st_size

    def open_file(self, path: str, mode: str = "rb") -> Union[BinaryIO, pafs.NativeFile]:
        """Open file for reading.

        Args:
            path: Local or S3 path
            mode: File mode (only 'rb' supported for S3)

        Returns:
            File-like object (BinaryIO for local files, NativeFile for S3)
        """
        if self.is_s3_path(path):
            normalized = self.normalize_s3_path(path)
            return self._s3_fs.open_input_file(normalized)
        else:
            return open(path, mode)

    def get_filesystem(self, path: str) -> pafs.FileSystem:
        """Get PyArrow filesystem for path.

        Args:
            path: Local or S3 path

        Returns:
            PyArrow filesystem instance
        """
        if self.is_s3_path(path):
            return self._s3_fs
        else:
            return self._local_fs
