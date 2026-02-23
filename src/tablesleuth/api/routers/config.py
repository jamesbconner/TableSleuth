"""Config API router."""

from __future__ import annotations

import dataclasses
import logging
import os
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from tablesleuth.config import (
    AppConfig,
    CatalogConfig,
    GizmoConfig,
    get_config_file_path,
    load_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])

_PYICEBERG_HOME = Path(os.getenv("PYICEBERG_HOME", Path.home()))
_PYICEBERG_YAML = _PYICEBERG_HOME / ".pyiceberg.yaml"


def _config_to_dict(cfg: AppConfig) -> dict[str, Any]:
    """Convert AppConfig to a serializable dict."""
    return {
        "catalog": dataclasses.asdict(cfg.catalog),
        "gizmosql": dataclasses.asdict(cfg.gizmosql),
    }


class ConfigUpdate(BaseModel):
    """Request body for PUT /config/."""

    catalog: dict[str, Any] | None = None
    gizmosql: dict[str, Any] | None = None


@router.get("/")
def get_config() -> dict[str, Any]:
    """Return the current AppConfig as JSON.

    Returns:
        Current configuration as a dictionary.
    """
    try:
        cfg = load_config()
        return _config_to_dict(cfg)
    except Exception as exc:
        logger.exception("Error loading config")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/")
def save_config(update: ConfigUpdate) -> dict[str, Any]:
    """Save updated configuration to tablesleuth.toml.

    Writes to the local (cwd) config file.

    Args:
        update: Partial config with catalog and/or gizmosql sections.

    Returns:
        Saved configuration as a dictionary.
    """
    try:
        # Load current config
        cfg = load_config()

        # Apply updates
        if update.catalog:
            cfg = AppConfig(
                catalog=CatalogConfig(default=update.catalog.get("default", cfg.catalog.default)),
                gizmosql=cfg.gizmosql,
            )
        if update.gizmosql:
            g = update.gizmosql
            cfg = AppConfig(
                catalog=cfg.catalog,
                gizmosql=GizmoConfig(
                    uri=g.get("uri", cfg.gizmosql.uri),
                    username=g.get("username", cfg.gizmosql.username),
                    password=g.get("password", cfg.gizmosql.password),
                    tls_skip_verify=g.get("tls_skip_verify", cfg.gizmosql.tls_skip_verify),
                ),
            )

        # Write to local config file
        config_path = Path.cwd() / "tablesleuth.toml"
        _write_toml(config_path, cfg)

        return {"saved": True, "path": str(config_path), "config": _config_to_dict(cfg)}
    except Exception as exc:
        logger.exception("Error saving config")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/upload")
async def upload_config(file: UploadFile) -> dict[str, Any]:
    """Upload a tablesleuth.toml file.

    Args:
        file: Uploaded TOML config file.

    Returns:
        Parsed configuration from uploaded file.
    """
    try:
        import tomllib

        content = await file.read()
        raw = tomllib.loads(content.decode("utf-8"))
        config_path = Path.cwd() / "tablesleuth.toml"
        config_path.write_bytes(content)
        return {"saved": True, "path": str(config_path), "raw": raw}
    except Exception as exc:
        logger.exception("Error uploading config")
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/pyiceberg")
def get_pyiceberg_config() -> dict[str, Any]:
    """Return the .pyiceberg.yaml contents.

    Returns:
        PyIceberg YAML as a dictionary, or empty dict if not found.
    """
    try:
        if _PYICEBERG_YAML.exists():
            with _PYICEBERG_YAML.open() as f:
                data = yaml.safe_load(f) or {}
            return {"exists": True, "path": str(_PYICEBERG_YAML), "config": data}
        return {"exists": False, "path": str(_PYICEBERG_YAML), "config": {}}
    except Exception as exc:
        logger.exception("Error reading .pyiceberg.yaml")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/pyiceberg/upload")
async def upload_pyiceberg_config(file: UploadFile) -> dict[str, Any]:
    """Upload a .pyiceberg.yaml file.

    Args:
        file: Uploaded YAML file.

    Returns:
        Confirmation with path written.
    """
    try:
        content = await file.read()
        # Validate YAML before saving
        parsed = yaml.safe_load(content.decode("utf-8"))
        if parsed is None:
            parsed = {}
        _PYICEBERG_YAML.parent.mkdir(parents=True, exist_ok=True)
        _PYICEBERG_YAML.write_bytes(content)
        return {"saved": True, "path": str(_PYICEBERG_YAML), "config": parsed}
    except yaml.YAMLError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {exc}") from exc
    except Exception as exc:
        logger.exception("Error uploading .pyiceberg.yaml")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/pyiceberg")
def save_pyiceberg_config(config: dict[str, Any]) -> dict[str, Any]:
    """Save updated .pyiceberg.yaml.

    Args:
        config: Full PyIceberg config dict to write.

    Returns:
        Confirmation with path written.
    """
    try:
        _PYICEBERG_YAML.parent.mkdir(parents=True, exist_ok=True)
        with _PYICEBERG_YAML.open("w") as f:
            yaml.dump(config, f, default_flow_style=False)
        return {"saved": True, "path": str(_PYICEBERG_YAML)}
    except Exception as exc:
        logger.exception("Error saving .pyiceberg.yaml")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status")
def get_config_status() -> dict[str, Any]:
    """Return active config file path and env var override status.

    Returns:
        Dictionary with config file path, env var overrides, and pyiceberg status.
    """
    try:
        config_path = get_config_file_path()
        env_overrides = {
            k: bool(os.getenv(k))
            for k in [
                "TABLESLEUTH_CONFIG",
                "TABLESLEUTH_CATALOG_NAME",
                "TABLESLEUTH_GIZMO_URI",
                "TABLESLEUTH_GIZMO_USERNAME",
                "TABLESLEUTH_GIZMO_PASSWORD",
                "TABLESLEUTH_CORS_ORIGINS",
            ]
        }
        return {
            "config_file": str(config_path) if config_path else None,
            "env_overrides": env_overrides,
            "pyiceberg_yaml_exists": _PYICEBERG_YAML.exists(),
            "pyiceberg_yaml_path": str(_PYICEBERG_YAML),
        }
    except Exception as exc:
        logger.exception("Error getting config status")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _write_toml(path: Path, cfg: AppConfig) -> None:
    """Write AppConfig to a TOML file.

    Args:
        path: Destination path.
        cfg: AppConfig to serialize.
    """
    lines = [
        "[catalog]",
        f'default = "{cfg.catalog.default}"' if cfg.catalog.default else "# default = ",
        "",
        "[gizmosql]",
        f'uri = "{cfg.gizmosql.uri}"',
        f'username = "{cfg.gizmosql.username}"',
        f'password = "{cfg.gizmosql.password}"',
        f"tls_skip_verify = {str(cfg.gizmosql.tls_skip_verify).lower()}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
