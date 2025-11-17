from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ColumnProfile(BaseModel):
    column: str
    row_count: int
    non_null_count: int
    null_count: int
    distinct_count: Optional[int] = None
    min_value: Any | None = None
    max_value: Any | None = None

    # New fields for enhanced statistics
    is_numeric: bool = False
    average: Optional[float] = None
    median: Optional[float] = None
    mode: Any | None = None
    mode_count: Optional[int] = None
    std_dev: Optional[float] = None
    variance: Optional[float] = None
    q1: Optional[float] = None  # 25th percentile
    q3: Optional[float] = None  # 75th percentile
