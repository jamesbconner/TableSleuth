"""GizmoSQL API router."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tablesleuth.config import load_config

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
