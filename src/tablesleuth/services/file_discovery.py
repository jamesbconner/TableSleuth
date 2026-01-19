from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tablesleuth.models.file_ref import FileRef

if TYPE_CHECKING:
    from tablesleuth.services.formats.iceberg import IcebergAdapter

logger = logging.getLogger(__name__)


def resolve_aws_region(region_override: str | None = None) -> str:
    """Resolve AWS region from multiple sources with priority order.

    Priority order:
    1. region_override parameter (--region flag)
    2. AWS_REGION environment variable
    3. AWS_DEFAULT_REGION environment variable
    4. Default: us-east-2

    Args:
        region_override: Optional region override from CLI flag

    Returns:
        Resolved AWS region string
    """
    if region_override:
        logger.debug(f"Using region from --region flag: {region_override}")
        return region_override

    env_region = os.getenv("AWS_REGION")
    if env_region:
        logger.debug(f"Using region from AWS_REGION env var: {env_region}")
        return env_region

    env_default_region = os.getenv("AWS_DEFAULT_REGION")
    if env_default_region:
        logger.debug(f"Using region from AWS_DEFAULT_REGION env var: {env_default_region}")
        return env_default_region

    default_region = "us-east-2"
    logger.debug(f"Using default region: {default_region}")
    return default_region


class FileDiscoveryService:
    """Service for discovering Parquet files from various sources.

    This service can discover Parquet files from:
    - Single file paths
    - Directory paths (with recursive scanning)
    - Iceberg tables via catalog
    - Glue Hive tables via AWS Glue catalog
    """

    def __init__(
        self,
        iceberg_adapter: IcebergAdapter | None = None,
        region: str | None = None,
    ) -> None:
        """Initialize the file discovery service.

        Args:
            iceberg_adapter: Optional IcebergAdapter instance for table-based discovery
            region: Optional AWS region override for Glue queries
        """
        self._valid_extensions = {".parquet", ".pq"}
        self._iceberg_adapter = iceberg_adapter
        self._resolved_region = resolve_aws_region(region)

    def discover_from_path(self, path: str | Path) -> list[FileRef]:
        """Discover Parquet files from a file or directory path.

        Supports both local paths and S3 paths (s3:// or s3a:// schemes).

        Args:
            path: Path to file or directory (local or S3)

        Returns:
            List of FileRef objects for discovered Parquet files

        Raises:
            FileNotFoundError: If path doesn't exist
            ValueError: If path is neither a file nor a directory
        """
        path_str = str(path)

        # Handle S3 paths (both s3:// and s3a:// schemes)
        if path_str.startswith("s3://") or path_str.startswith("s3a://"):
            return self._discover_from_s3_path(path_str)

        # Handle local paths
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

    def discover_from_glue_database(
        self, database_name: str, table_identifier: str
    ) -> list[FileRef]:
        """Discover Parquet files from a Glue Hive table.

        This method queries AWS Glue to get the table's S3 location and then
        discovers Parquet files from that location.

        Args:
            database_name: Glue database name (used as catalog name)
            table_identifier: Table identifier, either "table" or "database.table"

        Returns:
            List of FileRef objects for discovered Parquet files

        Raises:
            ValueError: If table is an Iceberg table (should use PyIceberg)
            Exception: If table not found or other Glue API errors
        """
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError as e:
            raise ImportError(
                "boto3 is required for Glue catalog access. Install with: pip install boto3"
            ) from e

        # Parse table identifier
        if "." in table_identifier:
            # Format: database.table
            parts = table_identifier.split(".", 1)
            db_name = parts[0]
            table_name = parts[1]
        else:
            # Format: table (use database_name as database)
            db_name = database_name
            table_name = table_identifier

        logger.info(
            f"Querying Glue for table '{table_name}' in database '{db_name}' "
            f"(region: {self._resolved_region})"
        )

        # Query Glue for table metadata
        try:
            glue_client = boto3.client("glue", region_name=self._resolved_region)
            response = glue_client.get_table(DatabaseName=db_name, Name=table_name)
            table_metadata = response["Table"]

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "EntityNotFoundException":
                raise ValueError(
                    f"Table not found in Glue: {db_name}.{table_name}\n"
                    f"Region: {self._resolved_region}\n"
                    f"Verify table exists with: aws glue get-table --database-name {db_name} "
                    f"--name {table_name} --region {self._resolved_region}\n"
                    f"If table is in a different region, use --region flag"
                ) from e
            else:
                raise ValueError(
                    f"Glue API error ({error_code}): {error_msg}\n"
                    f"Database: {db_name}, Table: {table_name}, Region: {self._resolved_region}"
                ) from e

        # Check if this is an Iceberg table
        table_params = table_metadata.get("Parameters", {})
        table_type = table_params.get("table_type", "").upper()

        if table_type == "ICEBERG":
            raise ValueError(
                f"Table '{db_name}.{table_name}' is an Iceberg table.\n"
                f"Add it to .pyiceberg.yaml instead:\n\n"
                f"catalog:\n"
                f"  {database_name}:\n"
                f"    type: glue\n"
                f"    region: {self._resolved_region}\n"
                f'    s3.access-key-id: ""\n'
                f'    s3.secret-access-key: ""\n'
                f'    s3.session-token: ""\n'
            )

        # Extract S3 location from StorageDescriptor
        storage_descriptor = table_metadata.get("StorageDescriptor", {})
        s3_location = storage_descriptor.get("Location")

        if not s3_location:
            raise ValueError(
                f"Table '{db_name}.{table_name}' has no S3 location in StorageDescriptor"
            )

        logger.info(f"Found S3 location for Hive table: {s3_location}")

        # Discover Parquet files from S3 location
        return self.discover_from_path(s3_location)

    def _discover_from_s3_path(self, s3_path: str) -> list[FileRef]:
        """Discover Parquet files from an S3 path.

        Args:
            s3_path: S3 path (s3://bucket/path or s3a://bucket/path)

        Returns:
            List of FileRef objects for discovered Parquet files

        Raises:
            FileNotFoundError: If S3 path doesn't exist
            ValueError: If S3 file is not a Parquet file
            ImportError: If required S3 dependencies not available
        """
        try:
            import pyarrow.fs as pafs
            from pyarrow.parquet import ParquetFile
        except ImportError as e:
            raise ImportError(
                "pyarrow is required for S3 access. Install with: pip install pyarrow"
            ) from e

        # Normalize S3 path - remove s3:// or s3a:// prefix for PyArrow
        if s3_path.startswith("s3a://"):
            normalized_path = s3_path[6:]  # Remove "s3a://"
            original_scheme = "s3a://"
        elif s3_path.startswith("s3://"):
            normalized_path = s3_path[5:]  # Remove "s3://"
            original_scheme = "s3://"
        else:
            normalized_path = s3_path
            original_scheme = "s3://"

        # Create S3 filesystem
        try:
            s3_fs = pafs.S3FileSystem(region=self._resolved_region)
        except Exception as e:
            logger.error(f"Failed to create S3 filesystem: {e}")
            raise

        # Check if path exists
        try:
            file_info = s3_fs.get_file_info(normalized_path)
        except Exception as e:
            raise FileNotFoundError(f"S3 path not found: {s3_path}") from e

        if file_info.type == pafs.FileType.NotFound:
            raise FileNotFoundError(f"S3 path not found: {s3_path}")

        parquet_files: list[FileRef] = []

        if file_info.type == pafs.FileType.File:
            # Single file - check if it's a Parquet file
            if not normalized_path.endswith((".parquet", ".pq")):
                raise ValueError(
                    f"File is not a Parquet file: {s3_path}\n"
                    f"File must have .parquet or .pq extension"
                )

            # Read row count from Parquet metadata
            record_count = None
            try:
                pf = ParquetFile(normalized_path, filesystem=s3_fs)
                record_count = pf.metadata.num_rows
            except Exception as e:
                logger.debug(f"Could not read record count from {s3_path}: {e}")

            parquet_files.append(
                FileRef(
                    path=s3_path,
                    file_size_bytes=file_info.size,
                    record_count=record_count,
                    source="s3",
                )
            )
        elif file_info.type == pafs.FileType.Directory:
            # Directory - scan recursively
            selector = pafs.FileSelector(normalized_path, recursive=True)
            try:
                file_infos = s3_fs.get_file_info(selector)
                for info in file_infos:
                    if info.type == pafs.FileType.File and info.path.endswith((".parquet", ".pq")):
                        # Reconstruct full S3 path with original scheme
                        full_s3_path = f"{original_scheme}{info.path}"
                        logger.debug(f"Discovered S3 file: {full_s3_path}")

                        # Read row count from Parquet metadata
                        record_count = None
                        try:
                            pf = ParquetFile(info.path, filesystem=s3_fs)
                            record_count = pf.metadata.num_rows
                            logger.debug(f"  Row count: {record_count}")
                        except Exception as e:
                            logger.debug(f"Could not read record count from {full_s3_path}: {e}")

                        parquet_files.append(
                            FileRef(
                                path=full_s3_path,
                                file_size_bytes=info.size,
                                record_count=record_count,
                                source="s3",
                            )
                        )
            except Exception as e:
                logger.error(f"Error scanning S3 directory {s3_path}: {e}")
                raise

        logger.info(f"Found {len(parquet_files)} Parquet files in S3 path: {s3_path}")
        return parquet_files

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
