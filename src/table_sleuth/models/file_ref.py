from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class FileRef:
    path: str
    content_type: str
    partition: Dict[str, Any]
    file_size_bytes: int
    record_count: int
    sequence_number: int
    data_sequence_number: int
    extra: Dict[str, Any] = field(default_factory=dict)
