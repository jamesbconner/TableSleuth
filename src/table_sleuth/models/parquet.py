from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ColumnStats:
    """Column-level statistics from Parquet metadata.

    Attributes:
        name: Column name
        physical_type: Physical storage type (e.g., INT64, BYTE_ARRAY)
        logical_type: Logical type annotation (e.g., UTF8, TIMESTAMP)
        null_count: Number of null values (None if unavailable)
        min_value: Minimum value from statistics (None if unavailable)
        max_value: Maximum value from statistics (None if unavailable)
        encodings: List of encoding types used
        compression: Compression codec name
        num_values: Total number of values in column (None if unavailable)
        distinct_count: Number of unique values (None if unavailable)
        total_compressed_size: Compressed size in bytes (None if unavailable)
        total_uncompressed_size: Uncompressed size in bytes (None if unavailable)
    """

    name: str
    physical_type: str
    logical_type: str | None
    null_count: int | None
    min_value: Any | None
    max_value: Any | None
    encodings: list[str]
    compression: str
    num_values: int | None
    distinct_count: int | None
    total_compressed_size: int | None
    total_uncompressed_size: int | None


@dataclass
class RowGroupInfo:
    """Row group metadata.

    Attributes:
        index: Row group index (0-based)
        num_rows: Number of rows in this row group
        total_byte_size: Total compressed size in bytes
        columns: Column statistics for this row group
    """

    index: int
    num_rows: int
    total_byte_size: int
    columns: list[ColumnStats]


@dataclass
class ParquetFileInfo:
    """Complete Parquet file metadata.

    Attributes:
        path: File path
        file_size_bytes: Total file size in bytes
        num_rows: Total number of rows
        num_row_groups: Number of row groups
        num_columns: Number of columns
        schema: Schema information (column name -> type info)
        row_groups: List of row group metadata
        columns: File-level column statistics
        created_by: Creator application string (None if unavailable)
        format_version: Parquet format version
    """

    path: str
    file_size_bytes: int
    num_rows: int
    num_row_groups: int
    num_columns: int
    schema: dict[str, Any]
    row_groups: list[RowGroupInfo]
    columns: list[ColumnStats]
    created_by: str | None
    format_version: str
