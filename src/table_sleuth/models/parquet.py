from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class ColumnStats:
    name: str
    physical_type: str
    logical_type: Optional[str]
    null_count: int
    min_value: Any | None
    max_value: Any | None
    encodings: List[str]
    compression: str


@dataclass
class ParquetFileInfo:
    path: str
    num_rows: int
    num_row_groups: int
    row_group_sizes: List[int]
    columns: List[ColumnStats]
