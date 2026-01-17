from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .file_ref import FileRef


@dataclass
class SnapshotInfo:
    snapshot_id: int
    parent_id: int | None
    timestamp_ms: int
    operation: str
    summary: dict[str, str]
    data_files: list[FileRef] = field(default_factory=list)
    delete_files: list[FileRef] = field(default_factory=list)
