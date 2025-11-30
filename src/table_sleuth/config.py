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
    default: str | None = None


@dataclass
class GizmoConfig:
    uri: str = "grpc+tls://localhost:31337"
    username: str = "gizmosql_username"
    password: str = "gizmosql_password"
    tls_skip_verify: bool = True


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


def load_config() -> AppConfig:
    raw = _load_toml_config()

    catalog_default = os.getenv("TABLE_SLEUTH_CATALOG_NAME") or raw.get("catalog", {}).get(
        "default"
    )

    gizmo_section = raw.get("gizmosql", {})

    gizmo = GizmoConfig(
        uri=os.getenv("TABLE_SLEUTH_GIZMO_URI", gizmo_section.get("uri", GizmoConfig.uri)),
        username=os.getenv(
            "TABLE_SLEUTH_GIZMO_USERNAME", gizmo_section.get("username", GizmoConfig.username)
        ),
        password=os.getenv(
            "TABLE_SLEUTH_GIZMO_PASSWORD", gizmo_section.get("password", GizmoConfig.password)
        ),
        tls_skip_verify=bool(gizmo_section.get("tls_skip_verify", GizmoConfig.tls_skip_verify)),
    )

    return AppConfig(catalog=CatalogConfig(default=catalog_default), gizmosql=gizmo)
