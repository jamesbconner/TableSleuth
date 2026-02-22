"""TableSleuth FastAPI application."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from tablesleuth import __version__
from tablesleuth.api.routers import config, delta, gizmosql, iceberg, parquet

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TableSleuth",
    description="REST API for Parquet, Iceberg, and Delta Lake forensic analysis.",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

_cors_origins_raw = os.getenv("TABLESLEUTH_CORS_ORIGINS", "http://localhost:3000")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
    """Return 404 for file-not-found errors."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Return 422 for value errors (bad input)."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return 500 for unexpected errors."""
    logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------------------
# Routers (all under /api prefix)
# ---------------------------------------------------------------------------

app.include_router(parquet.router, prefix="/api")
app.include_router(iceberg.router, prefix="/api")
app.include_router(delta.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(gizmosql.router, prefix="/api")


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["health"])
def health() -> dict[str, Any]:
    """Return server health status."""
    return {"status": "ok", "version": __version__}


# ---------------------------------------------------------------------------
# Static file serving (Next.js static export) — mounted LAST
# ---------------------------------------------------------------------------


def _resolve_web_dir() -> Path | None:
    """Resolve the web UI directory in priority order.

    Priority:
    1. TABLESLEUTH_WEB_UI_DIR env var
    2. Installed package: <package_root>/web
    3. Dev build: <repo_root>/web-ui/out

    Returns:
        Path to web directory if found, else None.
    """
    # 1. Env var override
    env_dir = os.getenv("TABLESLEUTH_WEB_UI_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p

    # 2. Installed package location
    pkg_web = Path(__file__).parent.parent / "web"
    if pkg_web.is_dir() and (pkg_web / "index.html").exists():
        return pkg_web

    # 3. Dev build output (repo checkout)
    dev_web = Path(__file__).parent.parent.parent.parent / "web-ui" / "out"
    if dev_web.is_dir() and (dev_web / "index.html").exists():
        return dev_web

    return None


_web_dir = _resolve_web_dir()

if _web_dir:
    logger.info("Serving web UI from: %s", _web_dir)
    # Next.js static export with trailingSlash:true generates a dedicated
    # index.html per route (e.g. settings/index.html, parquet/index.html).
    # StaticFiles(html=True) serves those automatically — no custom SPA
    # fallback needed, and adding one would intercept /_next/static/* asset
    # requests before they reach the file server.
    app.mount("/", StaticFiles(directory=str(_web_dir), html=True), name="static")
else:
    logger.warning(
        "Web UI directory not found. "
        "Run 'make build-release' or set TABLESLEUTH_WEB_UI_DIR to serve the frontend."
    )
