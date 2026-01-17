from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ColumnProfile(BaseModel):
    column: str
    row_count: int
    non_null_count: int
    null_count: int
    distinct_count: int | None = None
    min_value: Any | None = None
    max_value: Any | None = None

    # New fields for enhanced statistics
    is_numeric: bool = False
    average: float | None = None
    median: float | None = None
    mode: Any | None = None
    mode_count: int | None = None
    std_dev: float | None = None
    variance: float | None = None
    q1: float | None = None  # 25th percentile
    q3: float | None = None  # 75th percentile
