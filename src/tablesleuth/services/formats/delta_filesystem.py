"""Unified filesystem abstraction for Delta Lake transaction logs.

This module provides a clean interface for reading Delta Lake transaction logs
from both local and cloud storage, eliminating code duplication across the codebase.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tablesleuth.services.formats.delta_log_parser import DeltaLogParser
from tablesleuth.services.formats.delta_utils import get_filesystem_and_path

if TYPE_CHECKING:
    from pyarrow import fs as pafs

# Runtime import for cloud storage operations
try:
    from pyarrow import fs as pafs_runtime
except ImportError:
    pafs_runtime = None

logger = logging.getLogger(__name__)


class DeltaLogFileSystem:
    """Unified filesystem interface for Delta Lake transaction logs.

    This class abstracts the differences between local and cloud storage,
    providing a consistent API for reading Delta Lake transaction log files.

    Examples:
        >>> # Local table
        >>> fs = DeltaLogFileSystem("/path/to/table")
        >>> version_data = fs.read_version_file(0)

        >>> # S3 table
        >>> fs = DeltaLogFileSystem("s3://bucket/table", {"AWS_REGION": "us-west-2"})
        >>> if fs.version_file_exists(0):
        ...     data = fs.read_version_file(0)
    """

    def __init__(self, table_uri: str, storage_options: dict[str, str] | None = None):
        """Initialize filesystem for a Delta table.

        Args:
            table_uri: Table URI (local path or cloud URI like s3://bucket/path)
            storage_options: Optional cloud storage credentials and configuration
        """
        self._filesystem, self._table_path = get_filesystem_and_path(table_uri, storage_options)
        self._is_cloud = self._filesystem is not None

        # Build delta log path
        if self._is_cloud:
            # Cloud storage - use forward slashes
            self._delta_log_path_str = f"{self._table_path}/_delta_log"
            self._delta_log_path: Path | None = None
        else:
            # Local filesystem
            self._delta_log_path = Path(self._table_path) / "_delta_log"
            self._delta_log_path_str = str(self._delta_log_path)

    @property
    def is_cloud(self) -> bool:
        """Check if this is a cloud storage filesystem."""
        return self._is_cloud

    @property
    def table_path(self) -> str:
        """Get the normalized table path."""
        return self._table_path

    @property
    def delta_log_path(self) -> str:
        """Get the delta log directory path as a string."""
        return self._delta_log_path_str

    def get_version_file_path(self, version: int) -> str:
        """Get the path to a version file.

        Args:
            version: Version number

        Returns:
            Full path to the version file
        """
        if self._is_cloud:
            return f"{self._delta_log_path_str}/{version:020d}.json"
        else:
            assert self._delta_log_path is not None
            version_file_path = self._delta_log_path / f"{version:020d}.json"
            return str(version_file_path)

    def version_file_exists(self, version: int) -> bool:
        """Check if a version file exists.

        Args:
            version: Version number

        Returns:
            True if the version file exists
        """
        version_file = self.get_version_file_path(version)

        if self._is_cloud:
            assert self._filesystem is not None  # Type guard for mypy
            try:
                self._filesystem.get_file_info(version_file)
                return True
            except FileNotFoundError:
                return False
        else:
            return Path(version_file).exists()

    def read_version_file(self, version: int) -> dict[str, Any] | None:
        """Read and parse a version file.

        Args:
            version: Version number

        Returns:
            Parsed version file data, or None if file doesn't exist

        Examples:
            >>> fs = DeltaLogFileSystem("/path/to/table")
            >>> data = fs.read_version_file(0)
            >>> if data:
            ...     print(f"Add actions: {len(data['add_actions'])}")
            ...     print(f"Remove actions: {len(data['remove_actions'])}")
        """
        if not self.version_file_exists(version):
            return None

        version_file = self.get_version_file_path(version)

        try:
            return DeltaLogParser.parse_version_file(version_file, self._filesystem)
        except Exception as e:
            logger.debug(f"Failed to parse version file {version}: {e}")
            return None

    def file_exists(self, path: str) -> bool:
        """Check if a file exists (generic file, not just version files).

        Args:
            path: File path (relative to table root or absolute)

        Returns:
            True if the file exists
        """
        if self._is_cloud:
            assert self._filesystem is not None  # Type guard for mypy
            try:
                self._filesystem.get_file_info(path)
                return True
            except FileNotFoundError:
                return False
        else:
            return Path(path).exists()

    def get_file_size(self, path: str) -> int | None:
        """Get the size of a file in bytes.

        Args:
            path: File path

        Returns:
            File size in bytes, or None if file doesn't exist
        """
        if self._is_cloud:
            assert self._filesystem is not None  # Type guard for mypy
            try:
                file_info = self._filesystem.get_file_info(path)
                return file_info.size  # type: ignore[no-any-return]
            except FileNotFoundError:
                return None
        else:
            try:
                return Path(path).stat().st_size
            except FileNotFoundError:
                return None

    def list_checkpoint_files(self) -> list[str]:
        """List all checkpoint files in the delta log directory.

        Returns:
            List of checkpoint file paths

        Examples:
            >>> fs = DeltaLogFileSystem("/path/to/table")
            >>> checkpoints = fs.list_checkpoint_files()
            >>> for cp in checkpoints:
            ...     print(cp)
            00000000000000000010.checkpoint.parquet
            00000000000000000020.checkpoint.0000000001.0000000010.parquet
        """
        if self._is_cloud:
            assert self._filesystem is not None  # Type guard for mypy

            # Runtime import of pafs for cloud operations
            if pafs_runtime is None:
                raise ImportError(
                    "PyArrow is required for cloud storage support. "
                    "Install with: pip install pyarrow"
                )

            try:
                selector = pafs_runtime.FileSelector(self._delta_log_path_str, recursive=False)
                file_infos = self._filesystem.get_file_info(selector)

                checkpoint_files = []
                for file_info in file_infos:
                    # Use file_info.type to check if it's a file (not is_file attribute)
                    if (
                        file_info.type == pafs_runtime.FileType.File
                        and ".checkpoint." in file_info.path
                    ):
                        checkpoint_files.append(file_info.path)

                return checkpoint_files
            except Exception as e:
                logger.debug(f"Failed to list checkpoint files: {e}")
                return []
        else:
            assert self._delta_log_path is not None
            if not self._delta_log_path.exists():
                return []

            checkpoint_files = []
            for file_path in self._delta_log_path.iterdir():
                if file_path.is_file() and ".checkpoint." in file_path.name:
                    checkpoint_files.append(str(file_path))

            return checkpoint_files

    def get_checkpoint_file_size(self, checkpoint_path: str) -> int | None:
        """Get the size of a checkpoint file.

        Args:
            checkpoint_path: Path to checkpoint file

        Returns:
            File size in bytes, or None if file doesn't exist
        """
        if self._is_cloud:
            assert self._filesystem is not None  # Type guard for mypy
            try:
                file_info = self._filesystem.get_file_info(checkpoint_path)
                return file_info.size  # type: ignore[no-any-return]
            except FileNotFoundError:
                return None
        else:
            try:
                return Path(checkpoint_path).stat().st_size
            except FileNotFoundError:
                return None
