from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_PATHS = [
    Path.cwd() / "table_sleuth.toml",
    Path.home() / ".config" / "table_sleuth.toml",
]


@dataclass
class CatalogConfig:
    default: Optional[str] = None


@dataclass
class GizmoConfig:
    uri: str = "grpc+tls://localhost:31337"
    username: str = "gizmosql_username"
    password: str = "gizmosql_password"
    tls_skip_verify: bool = True
    # Docker volume mount configuration (optional - only needed for Docker deployments)
    local_data_path: str | None = None  # Local path that's mounted to Docker
    docker_data_path: str | None = None  # Path inside Docker container


@dataclass
class AppConfig:
    catalog: CatalogConfig
    gizmosql: GizmoConfig


def _load_toml_config() -> dict:
    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            with path.open("rb") as f:
                return tomllib.load(f)
    return {}


def _normalize_config_value(value: str | None) -> str | None:
    """Convert empty strings to None for optional configuration values.

    Args:
        value: Configuration value that may be None or an empty string

    Returns:
        None if value is None or empty string, otherwise the original value
    """
    return None if value == "" or value is None else value


def load_config() -> AppConfig:
    raw = _load_toml_config()

    catalog_default = os.getenv("TABLE_SLEUTH_CATALOG_NAME") or raw.get("catalog", {}).get(
        "default"
    )

    gizmo_section = raw.get("gizmosql", {})

    # Handle Docker path configuration - normalize empty strings to None
    # Precedence: env var (if set and not empty) → TOML config (if set and not empty) → dataclass default
    local_data_env = _normalize_config_value(os.getenv("TABLE_SLEUTH_LOCAL_DATA_PATH"))
    local_data_toml = _normalize_config_value(gizmo_section.get("local_data_path"))
    local_data_path = local_data_env or local_data_toml or GizmoConfig.local_data_path

    docker_data_env = _normalize_config_value(os.getenv("TABLE_SLEUTH_DOCKER_DATA_PATH"))
    docker_data_toml = _normalize_config_value(gizmo_section.get("docker_data_path"))
    docker_data_path = docker_data_env or docker_data_toml or GizmoConfig.docker_data_path

    gizmo = GizmoConfig(
        uri=os.getenv("TABLE_SLEUTH_GIZMO_URI", gizmo_section.get("uri", GizmoConfig.uri)),
        username=os.getenv(
            "TABLE_SLEUTH_GIZMO_USERNAME", gizmo_section.get("username", GizmoConfig.username)
        ),
        password=os.getenv(
            "TABLE_SLEUTH_GIZMO_PASSWORD", gizmo_section.get("password", GizmoConfig.password)
        ),
        tls_skip_verify=bool(gizmo_section.get("tls_skip_verify", GizmoConfig.tls_skip_verify)),
        local_data_path=local_data_path,
        docker_data_path=docker_data_path,
    )

    return AppConfig(catalog=CatalogConfig(default=catalog_default), gizmosql=gizmo)
