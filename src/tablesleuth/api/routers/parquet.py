"""Parquet API router."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tablesleuth.api.serialization import to_dict
from tablesleuth.services.file_discovery import FileDiscoveryService
from tablesleuth.services.formats.iceberg import IcebergAdapter
from tablesleuth.services.parquet_service import ParquetInspector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/parquet", tags=["parquet"])


class AnalyzeRequest(BaseModel):
    """Request body for /parquet/analyze."""

    path: str
    catalog_name: str | None = None
    region: str | None = None


class FileInfoRequest(BaseModel):
    """Request body for /parquet/file-info."""

    path: str
    region: str | None = None


class SampleRequest(BaseModel):
    """Request body for /parquet/sample."""

    path: str
    num_rows: int = 100
    region: str | None = None


@router.post("/analyze")
def analyze_parquet(req: AnalyzeRequest) -> dict[str, Any]:
    """Discover and inspect Parquet files at the given path.

    Args:
        req: Request containing path, optional catalog_name and region.

    Returns:
        Dictionary with discovered file refs and their basic metadata.
    """
    try:
        iceberg_adapter = IcebergAdapter(default_catalog=req.catalog_name)
        discovery = FileDiscoveryService(iceberg_adapter=iceberg_adapter, region=req.region)

        if req.catalog_name:
            file_refs = discovery.discover_from_table(
                table_identifier=req.path, catalog_name=req.catalog_name
            )
        else:
            file_refs = discovery.discover_from_path(req.path)

        return {"files": [to_dict(f) for f in file_refs], "count": len(file_refs)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error analyzing parquet path: %s", req.path)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/file-info")
def get_file_info(req: FileInfoRequest) -> dict[str, Any]:
    """Get detailed metadata for a single Parquet file.

    Args:
        req: Request containing the file path and optional region.

    Returns:
        ParquetFileInfo as a dictionary.
    """
    try:
        inspector = ParquetInspector(region=req.region)
        info = inspector.inspect_file(Path(req.path))
        result = to_dict(info)
        assert isinstance(result, dict)
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error inspecting parquet file: %s", req.path)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sample")
def get_sample(req: SampleRequest) -> dict[str, Any]:
    """Read a data sample from a Parquet file.

    Args:
        req: Request containing path, optional num_rows, and region.

    Returns:
        Dictionary with columns list and rows as list-of-lists.
    """
    try:
        import pyarrow.parquet as pq

        from tablesleuth.services.filesystem import FileSystem
        from tablesleuth.utils.path_utils import is_s3_path

        fs = FileSystem(region=req.region)
        path = req.path

        if is_s3_path(path):
            filesystem = fs.get_filesystem(path)
            normalized = fs.normalize_s3_path(path)
            pf = pq.ParquetFile(normalized, filesystem=filesystem)
        else:
            pf = pq.ParquetFile(path)

        # Read only the first batch to avoid loading entire file into memory
        batch_reader = pf.iter_batches(batch_size=req.num_rows, use_threads=False)
        table = next(batch_reader)
        columns = table.schema.names
        rows = table.to_pydict()
        rows_as_lists = [[rows[c][i] for c in columns] for i in range(len(table))]

        return {
            "columns": columns,
            "rows": rows_as_lists,
            "total_rows_in_file": pf.metadata.num_rows,
            "sampled_rows": len(table),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error reading parquet sample: %s", req.path)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
