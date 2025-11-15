from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TableHandle:
    native: Any
    format_name: str
