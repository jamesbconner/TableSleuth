from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from table_sleuth.models.file_ref import FileRef

if TYPE_CHECKING:
    from table_sleuth.services.formats.iceberg import IcebergAdapter

logger = logging.getLogger(__name__)


class FileDiscoveryService:
    """Service for discovering Parquet files from various sources.

    This service can discover Parquet files from:
    - Single file paths
    - Directory paths (with recursive scanning)
    - Iceberg tables via catalog (implemented in Task 3)
    """

    def __init__(self, iceberg_adapter: IcebergAdapter | None = None) -> None:
        """Initialize the file discovery service.

        Args:
            iceberg_adapter: Optional IcebergAdapter instance for table-based discovery
        """
        self._valid_extensions = {".parquet", ".pq"}
        self._iceberg_adapter = iceberg_adapter

    def discover_from_path(self, path: str | Path) -> list[FileRef]:
        """Discover Parquet files from a file or directory path.

        Args:
            path: Path to file or directory

        Returns:
            List of FileRef objects for discovered Parquet files

        Raises:
            FileNotFoundError: If path doesn't exist
            ValueError: If path is neither a file nor a directory
        """
        path_obj = Path(path)

        if not path_obj.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        if path_obj.is_file():
            # Single file
            if self._is_parquet_file(path_obj):
                return [self._create_file_ref(path_obj, source="direct")]
            else:
                raise ValueError(f"File is not a Parquet file: {path}")
        elif path_obj.is_dir():
            # Directory - scan for Parquet files
            parquet_files = self._scan_directory(path_obj)
            return [self._create_file_ref(f, source="directory") for f in parquet_files]
        else:
            raise ValueError(f"Path is neither a file nor a directory: {path}")

    def discover_from_table(self, table_identifier: str, catalog_name: str) -> list[FileRef]:
        """Discover Parquet files from an Iceberg table.

        Args:
            table_identifier: Iceberg table identifier (e.g., "db.table")
            catalog_name: Catalog name

        Returns:
            List of FileRef objects for table data files

        Raises:
            ValueError: If Iceberg adapter is not configured
            Exception: If catalog or table cannot be loaded
        """
        if self._iceberg_adapter is None:
            raise ValueError(
                "Iceberg adapter not configured. "
                "Initialize FileDiscoveryService with an IcebergAdapter instance."
            )

        try:
            # Use the Iceberg adapter to get data files
            return self._iceberg_adapter.get_data_files(table_identifier, catalog_name)
        except Exception as e:
            logger.error(f"Error discovering files from table {table_identifier}: {e}")
            raise

    def _is_parquet_file(self, path: Path) -> bool:
        """Check if a file is a Parquet file.

        Args:
            path: Path to file

        Returns:
            True if file appears to be a Parquet file
        """
        # Check extension
        if path.suffix.lower() not in self._valid_extensions:
            return False

        # Validate by checking for Parquet magic bytes
        try:
            with open(path, "rb") as f:
                # Parquet files have "PAR1" magic bytes at start
                header = f.read(4)
                if header != b"PAR1":
                    return False

                # Check footer (last 4 bytes)
                f.seek(-4, 2)  # Seek to 4 bytes before end
                footer = f.read(4)
                return footer == b"PAR1"
        except Exception as e:
            logger.debug(f"Error validating Parquet file {path}: {e}")
            return False

    def _scan_directory(self, directory: Path) -> list[Path]:
        """Recursively scan directory for Parquet files.

        Args:
            directory: Directory to scan

        Returns:
            List of Parquet file paths
        """
        parquet_files = []

        try:
            # Use rglob for recursive scanning
            for file_path in directory.rglob("*"):
                if file_path.is_file() and self._is_parquet_file(file_path):
                    parquet_files.append(file_path)
                    logger.debug(f"Found Parquet file: {file_path}")
        except PermissionError as e:
            logger.warning(f"Permission denied scanning directory {directory}: {e}")
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")

        return sorted(parquet_files)  # Sort for consistent ordering

    def _create_file_ref(self, path: Path, source: str) -> FileRef:
        """Create a FileRef object from a file path.

        Args:
            path: Path to Parquet file
            source: Source type ("direct" or "directory")

        Returns:
            FileRef object with basic metadata
        """
        file_size = path.stat().st_size

        # Try to get record count from Parquet metadata
        record_count = None
        try:
            from pyarrow.parquet import ParquetFile

            pf = ParquetFile(str(path))
            record_count = pf.metadata.num_rows
        except Exception as e:
            logger.debug(f"Could not read record count from {path}: {e}")

        return FileRef(
            path=str(path),
            file_size_bytes=file_size,
            record_count=record_count,
            source=source,
        )
