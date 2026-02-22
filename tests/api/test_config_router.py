"""Smoke tests for the Config API router."""

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed; run with --extra web")
pytest.importorskip("httpx", reason="httpx not installed; run with --extra web")

from fastapi.testclient import TestClient  # noqa: E402

from tablesleuth.api.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def test_get_config() -> None:
    """GET /api/config/ returns 200 with catalog and gizmosql keys."""
    response = client.get("/api/config/")
    assert response.status_code == 200
    data = response.json()
    assert "catalog" in data
    assert "gizmosql" in data
    assert "uri" in data["gizmosql"]


def test_config_status() -> None:
    """GET /api/config/status returns 200 with required keys."""
    response = client.get("/api/config/status")
    assert response.status_code == 200
    data = response.json()
    assert "config_file" in data
    assert "env_overrides" in data
    assert "pyiceberg_yaml_exists" in data


def test_get_pyiceberg() -> None:
    """GET /api/config/pyiceberg returns 200."""
    response = client.get("/api/config/pyiceberg")
    assert response.status_code == 200
    data = response.json()
    assert "exists" in data
    assert "config" in data
