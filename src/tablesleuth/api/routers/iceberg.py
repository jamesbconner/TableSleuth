"""Iceberg API router."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tablesleuth.exceptions import MetadataError, SnapshotNotFoundError, TableLoadError
from tablesleuth.services.iceberg_metadata_service import IcebergMetadataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iceberg", tags=["iceberg"])

_service = IcebergMetadataService()


def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses and nested objects to serializable dicts."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        d = {}
        for k, v in dataclasses.asdict(obj).items():
            if k == "native_table":
                continue  # Skip non-serializable pyiceberg Table object
            d[k] = _to_dict(v)
        return d
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


class LoadRequest(BaseModel):
    """Request body for /iceberg/load."""

    metadata_path: str | None = None
    catalog_name: str | None = None
    table_identifier: str | None = None


class CompareRequest(BaseModel):
    """Request body for /iceberg/compare."""

    metadata_path: str | None = None
    catalog_name: str | None = None
    table_identifier: str | None = None
    snapshot_a_id: int
    snapshot_b_id: int


@router.post("/load")
def load_table(req: LoadRequest) -> dict[str, Any]:
    """Load an Iceberg table and return metadata.

    Args:
        req: Request with metadata_path or catalog_name + table_identifier.

    Returns:
        IcebergTableInfo as a dictionary (excluding native_table).
    """
    try:
        table = _service.load_table(
            metadata_path=req.metadata_path,
            catalog_name=req.catalog_name,
            table_identifier=req.table_identifier,
        )
        return _to_dict(table)
    except TableLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error loading Iceberg table")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/snapshots")
def list_snapshots(req: LoadRequest) -> dict[str, Any]:
    """List all snapshots for an Iceberg table.

    Args:
        req: Request with metadata_path or catalog_name + table_identifier.

    Returns:
        Dictionary with list of IcebergSnapshotInfo objects.
    """
    try:
        table = _service.load_table(
            metadata_path=req.metadata_path,
            catalog_name=req.catalog_name,
            table_identifier=req.table_identifier,
        )
        snapshots = _service.list_snapshots(table)
        return {"snapshots": [_to_dict(s) for s in snapshots], "count": len(snapshots)}
    except TableLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error listing Iceberg snapshots")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/snapshot/{snapshot_id}")
def get_snapshot_details(snapshot_id: int, req: LoadRequest) -> dict[str, Any]:
    """Get detailed information for a specific snapshot.

    Args:
        snapshot_id: Snapshot ID to retrieve.
        req: Request with table location info.

    Returns:
        IcebergSnapshotDetails as a dictionary.
    """
    try:
        table = _service.load_table(
            metadata_path=req.metadata_path,
            catalog_name=req.catalog_name,
            table_identifier=req.table_identifier,
        )
        details = _service.get_snapshot_details(table, snapshot_id)
        return _to_dict(details)
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MetadataError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except TableLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error getting Iceberg snapshot details")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/compare")
def compare_snapshots(req: CompareRequest) -> dict[str, Any]:
    """Compare two snapshots and return differences.

    Args:
        req: Request with table location and two snapshot IDs.

    Returns:
        SnapshotComparison as a dictionary.
    """
    try:
        table = _service.load_table(
            metadata_path=req.metadata_path,
            catalog_name=req.catalog_name,
            table_identifier=req.table_identifier,
        )
        comparison = _service.compare_snapshots(table, req.snapshot_a_id, req.snapshot_b_id)
        return _to_dict(comparison)
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TableLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error comparing Iceberg snapshots")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/schema-evolution")
def get_schema_evolution(req: LoadRequest) -> dict[str, Any]:
    """Get schema evolution history for a table.

    Args:
        req: Request with table location info.

    Returns:
        Dictionary with list of SchemaInfo objects.
    """
    try:
        table = _service.load_table(
            metadata_path=req.metadata_path,
            catalog_name=req.catalog_name,
            table_identifier=req.table_identifier,
        )
        schemas = _service.get_schema_evolution(table)
        return {"schemas": [_to_dict(s) for s in schemas], "count": len(schemas)}
    except TableLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error getting Iceberg schema evolution")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
