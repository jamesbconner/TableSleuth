from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ColumnProfile(BaseModel):
    column: str
    row_count: int
    non_null_count: int
    null_count: int
    distinct_count: Optional[int]
    min_value: Any | None
    max_value: Any | None
