from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from tablesleuth.models import FileRef, SnapshotInfo


@dataclass
class FileMorImpact:
    file_path: str
    base_rows: int
    delete_rows_estimate: int
    effective_rows_estimate: int
    num_position_delete_files: int
    num_equality_delete_files: int


@dataclass
class SnapshotMorSummary:
    snapshot_id: int
    total_base_rows: int
    total_delete_rows_estimate: int
    total_effective_rows_estimate: int
    num_base_files: int
    num_delete_files: int
    file_impacts: list[FileMorImpact]


def estimate_mor(snapshot: SnapshotInfo) -> SnapshotMorSummary:
    delete_by_partition: dict[str, list[FileRef]] = {}

    for df in snapshot.delete_files:
        key = _partition_key(df.partition)
        delete_by_partition.setdefault(key, []).append(df)

    file_impacts: list[FileMorImpact] = []
    total_base_rows = 0
    total_delete_rows = 0

    for base in snapshot.data_files:
        key = _partition_key(base.partition)
        deletes = delete_by_partition.get(key, [])
        delete_rows = sum(d.record_count or 0 for d in deletes)

        base_rows = base.record_count or 0

        impact = FileMorImpact(
            file_path=base.path,
            base_rows=base_rows,
            delete_rows_estimate=delete_rows,
            effective_rows_estimate=max(0, base_rows - delete_rows),
            num_position_delete_files=sum(
                1 for d in deletes if d.content_type == "POSITION_DELETES"
            ),
            num_equality_delete_files=sum(
                1 for d in deletes if d.content_type == "EQUALITY_DELETES"
            ),
        )
        file_impacts.append(impact)
        total_base_rows += base_rows
        total_delete_rows += delete_rows

    return SnapshotMorSummary(
        snapshot_id=snapshot.snapshot_id,
        total_base_rows=total_base_rows,
        total_delete_rows_estimate=total_delete_rows,
        total_effective_rows_estimate=max(0, total_base_rows - total_delete_rows),
        num_base_files=len(snapshot.data_files),
        num_delete_files=len(snapshot.delete_files),
        file_impacts=file_impacts,
    )


def _partition_key(partition: dict) -> str:
    return "|".join(f"{k}={v}" for k, v in sorted(partition.items()))
