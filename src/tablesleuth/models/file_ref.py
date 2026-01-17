from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FileRef:
    """Reference to a Parquet file.

    This model supports both simple file references and
    Iceberg-specific metadata with full snapshot context.

    Attributes:
        path: File path (local or remote)
        file_size_bytes: File size in bytes
        record_count: Number of records (None if unknown)
        source: Source type ("direct", "directory", or "iceberg")
        content_type: Content type for Iceberg files (e.g., "DATA", "POSITION_DELETES")
        partition: Partition information for Iceberg files
        sequence_number: Sequence number for Iceberg files
        data_sequence_number: Data sequence number for Iceberg files
        extra: Additional metadata
    """

    path: str
    file_size_bytes: int
    record_count: int | None = None
    source: str = "direct"
    content_type: str = "DATA"
    partition: dict[str, Any] = field(default_factory=dict)
    sequence_number: int | None = None
    data_sequence_number: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)
