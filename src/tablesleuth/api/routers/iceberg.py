"""Iceberg API router."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tablesleuth.api.serialization import JS_MAX_SAFE_INT, to_dict
from tablesleuth.exceptions import MetadataError, SnapshotNotFoundError, TableLoadError
from tablesleuth.services.iceberg_metadata_service import IcebergMetadataService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/iceberg", tags=["iceberg"])

_service = IcebergMetadataService()


def _to_dict_iceberg(obj: Any) -> Any:
    """Convert Iceberg objects to dicts with special handling.
    
    - Skips native_table field (non-serializable PyIceberg Table object)
    - Includes @property values (computed metrics like delete_ratio)
    - Converts large integers to strings for JavaScript safety
    """
    return to_dict(
        obj,
        skip_fields={"native_table"},
        include_properties=True,
        safe_int_threshold=JS_MAX_SAFE_INT,
    )


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
    # Accept str or int — the frontend sends strings for int64 IDs to avoid
    # JavaScript float64 precision loss.
    snapshot_a_id: str | int
    snapshot_b_id: str | int


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
        result = _to_dict_iceberg(table)
        assert isinstance(result, dict)
        return result
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
        return {"snapshots": [_to_dict_iceberg(s) for s in snapshots], "count": len(snapshots)}
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
        result = _to_dict_iceberg(details)
        assert isinstance(result, dict)
        return result
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
        comparison = _service.compare_snapshots(
            table, int(req.snapshot_a_id), int(req.snapshot_b_id)
        )
        result = _to_dict_iceberg(comparison)
        assert isinstance(result, dict)
        return result
    except SnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TableLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error comparing Iceberg snapshots")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


_PYICEBERG_HOME = Path(os.getenv("PYICEBERG_HOME", str(Path.home())))
_PYICEBERG_YAML = _PYICEBERG_HOME / ".pyiceberg.yaml"


@router.get("/catalogs")
def list_catalogs() -> dict[str, Any]:
    """List catalog names defined in .pyiceberg.yaml.

    Returns:
        Dictionary with list of catalog names and the config file path.
    """
    try:
        if not _PYICEBERG_YAML.exists():
            return {"catalogs": [], "path": str(_PYICEBERG_YAML), "exists": False}
        with _PYICEBERG_YAML.open() as f:
            data = yaml.safe_load(f) or {}
        catalogs = list((data.get("catalog") or {}).keys())
        return {"catalogs": catalogs, "path": str(_PYICEBERG_YAML), "exists": True}
    except Exception as exc:
        logger.exception("Error reading catalog names from .pyiceberg.yaml")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class CatalogTablesRequest(BaseModel):
    """Request body for /iceberg/catalog-tables."""

    catalog_name: str


@router.post("/catalog-tables")
def list_catalog_tables(req: CatalogTablesRequest) -> dict[str, Any]:
    """List all tables available in a PyIceberg catalog.

    Enumerates namespaces then tables within each namespace.

    Args:
        req: Request with catalog_name matching a .pyiceberg.yaml entry.

    Returns:
        Dictionary with list of fully-qualified table identifiers.
    """
    try:
        from pyiceberg.catalog import load_catalog

        catalog = load_catalog(req.catalog_name)
        namespaces = catalog.list_namespaces()
        tables: list[str] = []
        for ns in namespaces:
            ns_str = ".".join(ns) if isinstance(ns, list | tuple) else str(ns)
            try:
                for tbl in catalog.list_tables(ns):
                    tables.append(".".join(tbl))
            except Exception as exc:
                # Some catalogs may have namespaces that cannot be listed
                logger.debug("Failed to list tables in namespace %s: %s", ns_str, exc)
                continue
        return {"tables": sorted(tables), "count": len(tables), "catalog": req.catalog_name}
    except TableLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error listing tables in catalog %s", req.catalog_name)
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
        return {"schemas": [_to_dict_iceberg(s) for s in schemas], "count": len(schemas)}
    except TableLoadError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error getting Iceberg schema evolution")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
