"""Delta Lake API router."""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tablesleuth.services.delta_forensics import DeltaForensics
from tablesleuth.services.formats.delta import DeltaAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/delta", tags=["delta"])


def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses and nested objects to serializable dicts."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    return obj


class LoadRequest(BaseModel):
    """Request body for /delta/load."""

    path: str
    version: int | None = None
    storage_options: dict[str, str] | None = None


@router.post("/load")
def load_table(req: LoadRequest) -> dict[str, Any]:
    """Load a Delta table and return current snapshot info.

    Args:
        req: Request with table path, optional version, and storage options.

    Returns:
        SnapshotInfo as a dictionary.
    """
    try:
        adapter = DeltaAdapter(storage_options=req.storage_options)
        handle = adapter.open_table(req.path)
        snapshot = adapter.load_snapshot(handle, req.version)
        result = _to_dict(snapshot)
        # Add native table version info
        result["current_version"] = handle.native.version()
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error loading Delta table: %s", req.path)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/versions")
def list_versions(req: LoadRequest) -> dict[str, Any]:
    """List all versions of a Delta table.

    Args:
        req: Request with table path and optional storage options.

    Returns:
        Dictionary with list of version snapshots.
    """
    try:
        adapter = DeltaAdapter(storage_options=req.storage_options)
        handle = adapter.open_table(req.path)
        snapshots = adapter.list_snapshots(handle)
        return {
            "versions": [_to_dict(s) for s in snapshots],
            "count": len(snapshots),
            "current_version": handle.native.version(),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error listing Delta versions: %s", req.path)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/forensics")
def get_forensics(req: LoadRequest) -> dict[str, Any]:
    """Run storage waste and file analysis on a Delta table.

    Args:
        req: Request with table path and optional storage options.

    Returns:
        Dictionary with forensics analysis results.
    """
    try:
        adapter = DeltaAdapter(storage_options=req.storage_options)
        handle = adapter.open_table(req.path)
        dt = handle.native
        snapshot = adapter.load_snapshot(handle, req.version)

        file_sizes = DeltaForensics.analyze_file_sizes(snapshot)
        storage_waste = DeltaForensics.analyze_storage_waste(
            dt, dt.version(), storage_options=req.storage_options
        )
        recommendations = DeltaForensics.generate_recommendations(
            dt, snapshot, storage_options=req.storage_options
        )
        checkpoint_health = DeltaForensics.analyze_checkpoint_health(
            dt, storage_options=req.storage_options
        )

        return {
            "path": req.path,
            "current_version": dt.version(),
            "file_size_analysis": file_sizes,
            "storage_waste": storage_waste,
            "checkpoint_health": checkpoint_health,
            "recommendations": recommendations,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error running Delta forensics: %s", req.path)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/schema")
def get_schema(req: LoadRequest) -> dict[str, Any]:
    """Get schema for a Delta table at a specific version.

    Args:
        req: Request with table path and optional version.

    Returns:
        Dictionary with list of schema fields.
    """
    try:
        from deltalake import DeltaTable as _DT

        kwargs: dict[str, Any] = {}
        if req.version is not None:
            kwargs["version"] = req.version
        if req.storage_options:
            kwargs["storage_options"] = req.storage_options
        dt = _DT(req.path, **kwargs)
        schema = dt.schema()
        fields = [
            {"name": f.name, "type": str(f.type), "nullable": f.nullable}
            for f in schema.fields
        ]
        return {"fields": fields, "count": len(fields)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error getting Delta schema: %s", req.path)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/schema-evolution")
def get_schema_evolution(req: LoadRequest) -> dict[str, Any]:
    """Get schema evolution history for a Delta table.

    Args:
        req: Request with table path and optional storage options.

    Returns:
        Dictionary with list of schema changes per version.
    """
    try:
        adapter = DeltaAdapter(storage_options=req.storage_options)
        handle = adapter.open_table(req.path)
        evolution = adapter.get_schema_evolution(handle)
        return {"evolution": evolution, "count": len(evolution)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error getting Delta schema evolution: %s", req.path)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
