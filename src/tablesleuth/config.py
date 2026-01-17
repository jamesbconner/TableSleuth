from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Configuration file search paths (in priority order)
# Priority: env var override > local > home > defaults
DEFAULT_CONFIG_PATHS = [
    Path.cwd() / "tablesleuth.toml",  # Local (project-level)
    Path.home() / "tablesleuth.toml",  # Home (user-level)
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
    """Load configuration from TOML file.

    Searches for config file in priority order:
    1. Path specified by TABLESLEUTH_CONFIG environment variable
    2. ./tablesleuth.toml (local/project-level)
    3. ~/tablesleuth.toml (home/user-level)

    Returns:
        Configuration dictionary, empty if no file found
    """
    # Check for environment variable override
    env_config_path = os.getenv("TABLESLEUTH_CONFIG")
    if env_config_path:
        path = Path(env_config_path)
        if path.exists():
            with path.open("rb") as f:
                return tomllib.load(f)
        # If specified but doesn't exist, that's an error
        raise FileNotFoundError(f"Config file specified by TABLESLEUTH_CONFIG not found: {path}")

    # Search default paths
    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            with path.open("rb") as f:
                return tomllib.load(f)

    return {}


def load_config() -> AppConfig:
    """Load application configuration.

    Configuration priority (highest to lowest):
    1. Environment variables (TABLESLEUTH_*)
    2. Local config file (./tablesleuth.toml)
    3. Home config file (~/tablesleuth.toml)
    4. Built-in defaults

    Returns:
        AppConfig with loaded settings

    Raises:
        FileNotFoundError: If TABLESLEUTH_CONFIG is set but file doesn't exist
    """
    raw = _load_toml_config()

    catalog_default = os.getenv("TABLESLEUTH_CATALOG_NAME") or raw.get("catalog", {}).get("default")

    gizmo_section = raw.get("gizmosql", {})

    gizmo = GizmoConfig(
        uri=os.getenv("TABLESLEUTH_GIZMO_URI", gizmo_section.get("uri", GizmoConfig.uri)),
        username=os.getenv(
            "TABLESLEUTH_GIZMO_USERNAME", gizmo_section.get("username", GizmoConfig.username)
        ),
        password=os.getenv(
            "TABLESLEUTH_GIZMO_PASSWORD", gizmo_section.get("password", GizmoConfig.password)
        ),
        tls_skip_verify=bool(gizmo_section.get("tls_skip_verify", GizmoConfig.tls_skip_verify)),
    )

    return AppConfig(catalog=CatalogConfig(default=catalog_default), gizmosql=gizmo)


def get_config_file_path() -> Path | None:
    """Get the path to the active configuration file.

    Returns:
        Path to config file being used, or None if using defaults

    Raises:
        FileNotFoundError: If TABLESLEUTH_CONFIG is set but file doesn't exist
    """
    env_config_path = os.getenv("TABLESLEUTH_CONFIG")
    if env_config_path:
        path = Path(env_config_path)
        if path.exists():
            return path
        # If specified but doesn't exist, that's an error (consistent with _load_toml_config)
        raise FileNotFoundError(f"Config file specified by TABLESLEUTH_CONFIG not found: {path}")

    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            return path

    return None
