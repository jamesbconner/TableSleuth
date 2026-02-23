"""GizmoSQL API router."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tablesleuth.config import load_config
from tablesleuth.models.iceberg import PerformanceComparison, QueryPerformanceMetrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gizmosql", tags=["gizmosql"])


class QueryRequest(BaseModel):
    """Request body for /gizmosql/query."""

    sql: str


class ProfileRequest(BaseModel):
    """Request body for /gizmosql/profile."""

    table_ref: str
    metadata_location: str | None = None
    snapshot_id: int | None = None
    columns: list[str] | None = None


def _get_profiler() -> Any:
    """Instantiate a GizmoDuckDbProfiler from current config.

    Returns:
        GizmoDuckDbProfiler instance.

    Raises:
        HTTPException: If GizmoSQL is not configured or not importable.
    """
    try:
        from tablesleuth.services.profiling.gizmo_duckdb import GizmoDuckDbProfiler
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="GizmoSQL profiling backend not available. Install adbc-driver-flightsql.",
        ) from exc

    cfg = load_config()
    return GizmoDuckDbProfiler(
        uri=cfg.gizmosql.uri,
        username=cfg.gizmosql.username,
        password=cfg.gizmosql.password,
        tls_skip_verify=cfg.gizmosql.tls_skip_verify,
    )


@router.get("/status")
def get_status() -> dict[str, Any]:
    """Test GizmoSQL connection and return status.

    Returns:
        Dictionary with connected flag, version (if connected), or error message.
    """
    try:
        profiler = _get_profiler()
        conn = profiler._connect()
        with conn, conn.cursor() as cur:
            cur.execute("SELECT version()")
            row = cur.fetchone()
            version = row[0] if row else "unknown"
        return {"connected": True, "version": version}
    except HTTPException:
        raise
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


@router.post("/query")
def execute_query(req: QueryRequest) -> dict[str, Any]:
    """Execute a SQL query against GizmoSQL.

    Args:
        req: Request with the SQL statement to execute.

    Returns:
        Dictionary with columns, rows, and elapsed_ms.
    """
    if not req.sql or not req.sql.strip():
        raise HTTPException(status_code=422, detail="SQL query cannot be empty")

    try:
        profiler = _get_profiler()
        start = time.perf_counter()
        conn = profiler._connect()
        with conn, conn.cursor() as cur:
            cur.execute(req.sql)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Serialize rows (convert any non-JSON-safe types to str)
        serialized_rows = []
        for row in rows:
            serialized_rows.append([str(v) if v is not None and not isinstance(v, (int, float, bool, str)) else v for v in row])

        return {
            "columns": columns,
            "rows": serialized_rows,
            "row_count": len(rows),
            "elapsed_ms": round(elapsed_ms, 2),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("GizmoSQL query error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/profile")
def profile_table(req: ProfileRequest) -> dict[str, Any]:
    """Profile columns of an Iceberg table via GizmoSQL.

    Args:
        req: Request with table_ref, optional metadata_location, snapshot_id, columns.

    Returns:
        Dictionary mapping column names to ColumnProfile dicts.
    """
    try:
        profiler = _get_profiler()

        if req.metadata_location:
            profiler.register_iceberg_table_with_snapshot(
                req.table_ref, req.metadata_location, req.snapshot_id
            )
            view_name = req.table_ref
        else:
            view_name = req.table_ref

        if req.columns:
            profiles = profiler.profile_columns(view_name, req.columns)
        else:
            raise HTTPException(
                status_code=422, detail="columns list is required for profile endpoint"
            )

        return {col: prof.model_dump() for col, prof in profiles.items()}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("GizmoSQL profile error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class CompareRequest(BaseModel):
    """Request body for /gizmosql/compare."""

    format: Literal["iceberg", "delta"]
    # Iceberg table reference (one of metadata_path or catalog_name+table_identifier)
    metadata_path: str | None = None
    catalog_name: str | None = None
    table_identifier: str | None = None
    # Delta table reference
    path: str | None = None
    storage_options: dict[str, str] | None = None
    # Snapshot / version IDs — strings to handle int64 Iceberg snapshot IDs safely
    id_a: str
    id_b: str
    # Query template; {table} is replaced at runtime
    query: str


def _serialize_metrics(m: QueryPerformanceMetrics) -> dict[str, Any]:
    return {
        "execution_time_ms": m.execution_time_ms,
        "files_scanned": m.files_scanned,
        "bytes_scanned": m.bytes_scanned,
        "rows_scanned": m.rows_scanned,
        "rows_returned": m.rows_returned,
        "memory_peak_mb": m.memory_peak_mb,
        "scan_efficiency": m.scan_efficiency,
    }


def _serialize_comparison(c: PerformanceComparison) -> dict[str, Any]:
    return {
        "query": c.query,
        "table_a_name": c.table_a_name,
        "table_b_name": c.table_b_name,
        "metrics_a": _serialize_metrics(c.metrics_a),
        "metrics_b": _serialize_metrics(c.metrics_b),
        "execution_time_delta_pct": c.execution_time_delta_pct,
        "files_scanned_delta_pct": c.files_scanned_delta_pct,
        "analysis": c.analysis,
    }


@router.post("/compare")
def compare_performance(req: CompareRequest) -> dict[str, Any]:
    """Compare query performance between two Iceberg snapshots or Delta versions.

    Registers both table versions with the GizmoDuckDbProfiler, executes the
    query template against each, and returns side-by-side metrics with analysis.

    Args:
        req: Request with format, table location, two IDs, and query template.

    Returns:
        Serialized PerformanceComparison with metrics and analysis text.
    """
    try:
        from tablesleuth.services.snapshot_performance_analyzer import SnapshotPerformanceAnalyzer

        profiler = _get_profiler()

        if req.format == "iceberg":
            from tablesleuth.services.iceberg_manifest_patch import patched_iceberg_metadata
            from tablesleuth.services.iceberg_metadata_service import IcebergMetadataService

            service = IcebergMetadataService()
            table = service.load_table(
                metadata_path=req.metadata_path,
                catalog_name=req.catalog_name,
                table_identifier=req.table_identifier,
            )
            native = table.native_table
            id_a, id_b = int(req.id_a), int(req.id_b)

            # Use iceberg_scan() so that delete files (positional / equality) are
            # applied during the query — this is the whole point of MOR comparison.
            # DuckDB's iceberg extension rejects delete-file entries whose file_format
            # is stored as 'PARQUET' (uppercase) in the manifest avro files.
            # patched_iceberg_metadata() creates a lightweight local copy of the
            # metadata chain with that string lowercased, redirecting only the affected
            # delete manifests; all data files remain at their original S3/local paths.
            with (
                patched_iceberg_metadata(native, id_a) as meta_a,
                patched_iceberg_metadata(native, id_b) as meta_b,
            ):
                profiler.register_iceberg_table_with_snapshot("snap_a", meta_a, id_a)
                profiler.register_iceberg_table_with_snapshot("snap_b", meta_b, id_b)

                analyzer = SnapshotPerformanceAnalyzer(profiler)
                comparison = analyzer.compare_query_performance("snap_a", "snap_b", req.query)
                return _serialize_comparison(comparison)

        elif req.format == "delta":
            if not req.path:
                raise ValueError("path is required for delta format")
            profiler.register_delta_table_with_version("ver_a", req.path, int(req.id_a))
            profiler.register_delta_table_with_version("ver_b", req.path, int(req.id_b))
            label_a, label_b = "ver_a", "ver_b"

        else:
            raise ValueError(f"Unsupported format: {req.format}")

        analyzer = SnapshotPerformanceAnalyzer(profiler)
        comparison = analyzer.compare_query_performance(label_a, label_b, req.query)
        return _serialize_comparison(comparison)

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("GizmoSQL comparison error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
