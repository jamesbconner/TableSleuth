from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pyarrow.fs as pafs
from pyarrow.parquet import ParquetFile

from tablesleuth.models.parquet import ColumnStats, ParquetFileInfo, RowGroupInfo
from tablesleuth.services.filesystem import FileSystem
from tablesleuth.utils.path_utils import is_s3_path

logger = logging.getLogger(__name__)


class ParquetInspector:
    """Service for extracting Parquet file metadata using PyArrow.

    This service provides methods to inspect Parquet files and extract
    detailed metadata including schema, row groups, and column statistics.
    Supports both local and S3 file paths.
    """

    def __init__(self, region: str | None = None):
        """Initialize ParquetInspector with filesystem support.

        Args:
            region: AWS region for S3 access. If None, uses AWS_REGION or AWS_DEFAULT_REGION
                   environment variable, or defaults to "us-east-2"
        """
        self._fs = FileSystem(region=region)

    def inspect_file(self, file_path: str | Path) -> ParquetFileInfo:
        """Extract complete metadata from a Parquet file.

        Args:
            file_path: Path to Parquet file (local or S3)

        Returns:
            ParquetFileInfo with schema, row groups, and column stats

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is not a valid Parquet file
        """
        file_path_str = str(file_path)

        if not self._fs.exists(file_path_str):
            raise FileNotFoundError(f"File not found: {file_path_str}")

        try:
            # Open file with appropriate filesystem
            if is_s3_path(file_path_str):
                filesystem = self._fs.get_filesystem(file_path_str)
                normalized_path = self._fs.normalize_s3_path(file_path_str)
                pf = ParquetFile(normalized_path, filesystem=filesystem)
            else:
                pf = ParquetFile(file_path_str)
        except Exception as e:
            raise ValueError(f"Invalid Parquet file: {e}") from e

        md = pf.metadata
        schema = pf.schema_arrow

        # Get file size
        file_size_bytes = self._fs.get_size(file_path_str)

        # Extract schema information
        schema_dict = self._extract_schema(schema)

        # Extract row group information
        row_groups = self.get_row_groups(file_path)

        # Extract file-level column statistics
        columns = self._extract_file_level_columns(pf, md, schema)

        # Get metadata
        created_by = md.created_by if hasattr(md, "created_by") else None
        format_version = md.format_version if hasattr(md, "format_version") else "unknown"

        return ParquetFileInfo(
            path=file_path_str,
            file_size_bytes=file_size_bytes,
            num_rows=md.num_rows,
            num_row_groups=md.num_row_groups,
            num_columns=md.num_columns,
            schema=schema_dict,
            row_groups=row_groups,
            columns=columns,
            created_by=created_by,
            format_version=str(format_version),
        )

    def get_schema(self, file_path: str | Path) -> dict[str, dict[str, str]]:
        """Extract schema information from Parquet file.

        Args:
            file_path: Path to Parquet file (local or S3)

        Returns:
            Dictionary mapping column names to type information
        """
        file_path_str = str(file_path)
        if is_s3_path(file_path_str):
            filesystem = self._fs.get_filesystem(file_path_str)
            normalized_path = self._fs.normalize_s3_path(file_path_str)
            pf = ParquetFile(normalized_path, filesystem=filesystem)
        else:
            pf = ParquetFile(file_path_str)
        return self._extract_schema(pf.schema_arrow)

    def get_row_groups(self, file_path: str | Path) -> list[RowGroupInfo]:
        """Extract row group information from Parquet file.

        Args:
            file_path: Path to Parquet file (local or S3)

        Returns:
            List of RowGroupInfo objects
        """
        file_path_str = str(file_path)
        if is_s3_path(file_path_str):
            filesystem = self._fs.get_filesystem(file_path_str)
            normalized_path = self._fs.normalize_s3_path(file_path_str)
            pf = ParquetFile(normalized_path, filesystem=filesystem)
        else:
            pf = ParquetFile(file_path_str)
        md = pf.metadata
        schema = pf.schema_arrow

        row_groups = []
        for rg_idx in range(md.num_row_groups):
            rg_md = md.row_group(rg_idx)

            # Extract column stats for this row group
            columns = []
            for col_idx in range(md.num_columns):
                col_md = rg_md.column(col_idx)
                col_schema = md.schema.column(col_idx)
                col_name = col_schema.name

                # Try to find field in schema, handle nested columns
                field = None
                try:
                    field = schema.field(col_name)
                except KeyError:
                    # For nested columns, the name might be a path
                    logger.debug(f"Column {col_name} not found in top-level schema")

                columns.append(
                    self._extract_column_stats(
                        col_name=col_name,
                        col_schema=col_schema,
                        field=field,
                        col_metadata=[col_md],
                    )
                )

            row_groups.append(
                RowGroupInfo(
                    index=rg_idx,
                    num_rows=rg_md.num_rows,
                    total_byte_size=rg_md.total_byte_size,
                    columns=columns,
                )
            )

        return row_groups

    def get_column_stats(self, file_path: str | Path, column_name: str) -> ColumnStats:
        """Extract statistics for a specific column.

        Args:
            file_path: Path to Parquet file
            column_name: Name of column to extract stats for

        Returns:
            ColumnStats for the specified column

        Raises:
            ValueError: If column doesn't exist
        """
        file_path_str = str(file_path)
        if is_s3_path(file_path_str):
            filesystem = self._fs.get_filesystem(file_path_str)
            normalized_path = self._fs.normalize_s3_path(file_path_str)
            pf = ParquetFile(normalized_path, filesystem=filesystem)
        else:
            pf = ParquetFile(file_path_str)
        md = pf.metadata
        schema = pf.schema_arrow

        # Find column index
        col_idx = None
        for idx in range(md.num_columns):
            if md.schema.column(idx).name == column_name:
                col_idx = idx
                break

        if col_idx is None:
            raise ValueError(f"Column '{column_name}' not found in file")

        col_schema = md.schema.column(col_idx)

        # Try to find field in schema, handle nested columns
        field = None
        try:
            field = schema.field(column_name)
        except KeyError:
            logger.debug(f"Column {column_name} not found in top-level schema")

        # Collect metadata from all row groups
        row_group_cols = [md.row_group(rg).column(col_idx) for rg in range(md.num_row_groups)]

        return self._extract_column_stats(
            col_name=column_name,
            col_schema=col_schema,
            field=field,
            col_metadata=row_group_cols,
        )

    def _extract_schema(self, schema: Any) -> dict[str, dict[str, str]]:
        """Extract schema information from PyArrow schema.

        Args:
            schema: PyArrow schema object

        Returns:
            Dictionary mapping column names to type information
        """
        schema_dict = {}
        for field in schema:
            schema_dict[field.name] = {
                "type": str(field.type),
                "nullable": field.nullable,
            }
        return schema_dict

    def _extract_file_level_columns(
        self, pf: ParquetFile, md: Any, schema: Any
    ) -> list[ColumnStats]:
        """Extract file-level column statistics.

        Args:
            pf: ParquetFile object
            md: File metadata
            schema: PyArrow schema

        Returns:
            List of ColumnStats for all columns
        """
        columns = []

        for col_idx in range(md.num_columns):
            col_schema = md.schema.column(col_idx)
            col_name = col_schema.name

            # Try to find field in schema, handle nested columns
            field = None
            try:
                field = schema.field(col_name)
            except KeyError:
                # For nested columns, the name might be a path
                logger.debug(f"Column {col_name} not found in top-level schema")

            # Collect metadata from all row groups
            row_group_cols = [md.row_group(rg).column(col_idx) for rg in range(md.num_row_groups)]

            columns.append(
                self._extract_column_stats(
                    col_name=col_name,
                    col_schema=col_schema,
                    field=field,
                    col_metadata=row_group_cols,
                )
            )

        return columns

    def _extract_column_stats(
        self, col_name: str, col_schema: Any, field: Any, col_metadata: list[Any]
    ) -> ColumnStats:
        """Extract statistics for a column from metadata.

        Args:
            col_name: Column name
            col_schema: Parquet column schema
            field: PyArrow field
            col_metadata: List of column metadata from row groups

        Returns:
            ColumnStats object
        """
        # Calculate null count
        null_count = None
        try:
            null_counts = [c.num_nulls for c in col_metadata if c.num_nulls is not None]
            if null_counts:
                null_count = sum(null_counts)
        except Exception as e:
            logger.debug(f"Could not calculate null count for {col_name}: {e}")

        # Get physical and logical types
        physical_type = (
            col_schema.physical_type.name
            if hasattr(col_schema.physical_type, "name")
            else str(col_schema.physical_type)
        )
        logical_type = str(field.type) if field else None

        # Extract min/max values
        min_value = None
        max_value = None
        try:
            mins = []
            maxs = []
            for c in col_metadata:
                if c.statistics is not None and c.statistics.has_min_max:
                    try:
                        mins.append(c.statistics.min)
                        maxs.append(c.statistics.max)
                    except Exception as e:
                        # PyArrow can't extract stats for some types (e.g., DECIMAL stored as INT64)
                        logger.debug(f"Could not extract min/max for {col_name} in row group: {e}")
                        continue

            if mins:
                min_value = min(mins)
            if maxs:
                max_value = max(maxs)
        except Exception as e:
            logger.debug(f"Could not extract min/max for {col_name}: {e}")

        # Get compression and encodings
        compression = "unknown"
        encodings = []
        try:
            if col_metadata:
                first_col = col_metadata[0]
                compression_obj = first_col.compression
                compression = (
                    compression_obj.name
                    if hasattr(compression_obj, "name")
                    else str(compression_obj)
                )

                # Collect unique encodings across all row groups
                encoding_set = set()
                for c in col_metadata:
                    if c.encodings:
                        for enc in c.encodings:
                            encoding_set.add(enc.name if hasattr(enc, "name") else str(enc))
                encodings = sorted(list(encoding_set))
        except Exception as e:
            logger.debug(f"Could not extract compression/encodings for {col_name}: {e}")

        # Extract num_values (sum across all row groups)
        num_values = None
        try:
            num_values_list = [c.num_values for c in col_metadata if c.num_values is not None]
            if num_values_list:
                num_values = sum(num_values_list)
        except Exception as e:
            logger.debug(f"Could not calculate num_values for {col_name}: {e}")

        # Extract distinct_count (from statistics, if available)
        distinct_count = None
        try:
            # Distinct count is rarely populated, check first row group
            if col_metadata and col_metadata[0].statistics:
                distinct_count = col_metadata[0].statistics.distinct_count
        except Exception as e:
            logger.debug(f"Could not extract distinct_count for {col_name}: {e}")

        # Extract sizes (sum across all row groups)
        total_compressed_size = None
        total_uncompressed_size = None
        try:
            compressed_sizes = [
                c.total_compressed_size for c in col_metadata if c.total_compressed_size is not None
            ]
            if compressed_sizes:
                total_compressed_size = sum(compressed_sizes)

            uncompressed_sizes = [
                c.total_uncompressed_size
                for c in col_metadata
                if c.total_uncompressed_size is not None
            ]
            if uncompressed_sizes:
                total_uncompressed_size = sum(uncompressed_sizes)
        except Exception as e:
            logger.debug(f"Could not extract sizes for {col_name}: {e}")

        return ColumnStats(
            name=col_name,
            physical_type=physical_type,
            logical_type=logical_type,
            null_count=null_count,
            min_value=min_value,
            max_value=max_value,
            encodings=encodings,
            compression=compression,
            num_values=num_values,
            distinct_count=distinct_count,
            total_compressed_size=total_compressed_size,
            total_uncompressed_size=total_uncompressed_size,
        )
