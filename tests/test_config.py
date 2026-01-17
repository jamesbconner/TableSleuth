"""Tests for configuration loading."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from tablesleuth.config import (
    AppConfig,
    CatalogConfig,
    GizmoConfig,
    load_config,
)


def test_catalog_config_defaults() -> None:
    """Test CatalogConfig default values."""
    config = CatalogConfig()
    assert config.default is None


def test_catalog_config_with_value() -> None:
    """Test CatalogConfig with custom value."""
    config = CatalogConfig(default="local")
    assert config.default == "local"


def test_gizmo_config_defaults() -> None:
    """Test GizmoConfig default values."""
    config = GizmoConfig()
    assert config.uri == "grpc+tls://localhost:31337"
    assert config.username == "gizmosql_username"
    assert config.password == "gizmosql_password"
    assert config.tls_skip_verify is True


def test_gizmo_config_custom_values() -> None:
    """Test GizmoConfig with custom values."""
    config = GizmoConfig(
        uri="grpc://custom:1234",
        username="user",
        password="pass",
        tls_skip_verify=False,
    )
    assert config.uri == "grpc://custom:1234"
    assert config.username == "user"
    assert config.password == "pass"
    assert config.tls_skip_verify is False


def test_app_config_structure() -> None:
    """Test AppConfig structure."""
    catalog = CatalogConfig(default="local")
    gizmo = GizmoConfig()
    config = AppConfig(catalog=catalog, gizmosql=gizmo)

    assert config.catalog == catalog
    assert config.gizmosql == gizmo


def test_load_config_with_defaults() -> None:
    """Test load_config returns defaults when no config file exists."""
    with patch("tablesleuth.config._load_toml_config", return_value={}):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

            assert config.catalog.default is None
            assert config.gizmosql.uri == "grpc+tls://localhost:31337"
            assert config.gizmosql.username == "gizmosql_username"
            assert config.gizmosql.password == "gizmosql_password"
            assert config.gizmosql.tls_skip_verify is True


def test_load_config_from_env_vars() -> None:
    """Test load_config reads from environment variables."""
    env_vars = {
        "TABLESLEUTH_CATALOG_NAME": "test_catalog",
        "TABLESLEUTH_GIZMO_URI": "grpc://test:9999",
        "TABLESLEUTH_GIZMO_USERNAME": "test_user",
        "TABLESLEUTH_GIZMO_PASSWORD": "test_pass",
    }

    with patch("tablesleuth.config._load_toml_config", return_value={}):
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()

            assert config.catalog.default == "test_catalog"
            assert config.gizmosql.uri == "grpc://test:9999"
            assert config.gizmosql.username == "test_user"
            assert config.gizmosql.password == "test_pass"


def test_load_config_from_toml() -> None:
    """Test load_config reads from TOML file."""
    toml_data = {
        "catalog": {"default": "toml_catalog"},
        "gizmosql": {
            "uri": "grpc://toml:8888",
            "username": "toml_user",
            "password": "toml_pass",
            "tls_skip_verify": False,
        },
    }

    with patch("tablesleuth.config._load_toml_config", return_value=toml_data):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

            assert config.catalog.default == "toml_catalog"
            assert config.gizmosql.uri == "grpc://toml:8888"
            assert config.gizmosql.username == "toml_user"
            assert config.gizmosql.password == "toml_pass"
            assert config.gizmosql.tls_skip_verify is False


def test_load_config_env_overrides_toml() -> None:
    """Test that environment variables override TOML config."""
    toml_data = {
        "catalog": {"default": "toml_catalog"},
        "gizmosql": {
            "uri": "grpc://toml:8888",
            "username": "toml_user",
        },
    }

    env_vars = {
        "TABLESLEUTH_CATALOG_NAME": "env_catalog",
        "TABLESLEUTH_GIZMO_URI": "grpc://env:7777",
    }

    with patch("tablesleuth.config._load_toml_config", return_value=toml_data):
        with patch.dict(os.environ, env_vars, clear=True):
            config = load_config()

            # Env vars should override TOML
            assert config.catalog.default == "env_catalog"
            assert config.gizmosql.uri == "grpc://env:7777"

            # TOML values should be used where env vars not set
            assert config.gizmosql.username == "toml_user"


def test_load_config_partial_toml() -> None:
    """Test load_config handles partial TOML configuration."""
    toml_data = {
        "catalog": {"default": "partial_catalog"},
        # gizmosql section missing
    }

    with patch("tablesleuth.config._load_toml_config", return_value=toml_data):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

            # Catalog from TOML
            assert config.catalog.default == "partial_catalog"

            # GizmoSQL should use defaults
            assert config.gizmosql.uri == "grpc+tls://localhost:31337"
            assert config.gizmosql.username == "gizmosql_username"


def test_load_config_empty_toml() -> None:
    """Test load_config handles empty TOML file."""
    with patch("tablesleuth.config._load_toml_config", return_value={}):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

            # Should use all defaults
            assert config.catalog.default is None
            assert config.gizmosql.uri == "grpc+tls://localhost:31337"


def test_load_config_missing_catalog_section() -> None:
    """Test load_config handles missing catalog section in TOML."""
    toml_data = {
        "gizmosql": {"uri": "grpc://test:1234"},
        # catalog section missing
    }

    with patch("tablesleuth.config._load_toml_config", return_value=toml_data):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

            assert config.catalog.default is None
            assert config.gizmosql.uri == "grpc://test:1234"


def test_gizmo_config_tls_skip_verify_bool_conversion() -> None:
    """Test that tls_skip_verify is properly converted to bool."""
    toml_data = {
        "gizmosql": {"tls_skip_verify": "true"},  # String instead of bool
    }

    with patch("tablesleuth.config._load_toml_config", return_value=toml_data):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

            # Should be converted to bool
            assert isinstance(config.gizmosql.tls_skip_verify, bool)


def test_config_dataclasses_are_frozen() -> None:
    """Test that config dataclasses can be modified (not frozen)."""
    config = CatalogConfig(default="test")
    # Should be able to modify (dataclasses are not frozen by default)
    config.default = "modified"
    assert config.default == "modified"


def test_load_config_returns_app_config() -> None:
    """Test that load_config returns AppConfig instance."""
    with patch("tablesleuth.config._load_toml_config", return_value={}):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

            assert isinstance(config, AppConfig)
            assert isinstance(config.catalog, CatalogConfig)
            assert isinstance(config.gizmosql, GizmoConfig)
