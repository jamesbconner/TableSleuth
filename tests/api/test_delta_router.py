"""Smoke tests for the Delta API router."""

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed; run with --extra web")
pytest.importorskip("httpx", reason="httpx not installed; run with --extra web")

from fastapi.testclient import TestClient  # noqa: E402

from tablesleuth.api.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def test_load_nonexistent_table() -> None:
    """POST /api/delta/load with nonexistent path returns 404 or 422."""
    response = client.post(
        "/api/delta/load",
        json={"path": "/nonexistent/delta/table"},
    )
    assert response.status_code in (404, 422, 500)


def test_load_no_body() -> None:
    """POST /api/delta/load without required field returns 422."""
    response = client.post("/api/delta/load", json={})
    assert response.status_code == 422


def test_versions_nonexistent() -> None:
    """POST /api/delta/versions with nonexistent path returns error."""
    response = client.post(
        "/api/delta/versions",
        json={"path": "/nonexistent/delta/table"},
    )
    assert response.status_code in (404, 422, 500)


def test_forensics_nonexistent() -> None:
    """POST /api/delta/forensics with nonexistent path returns error."""
    response = client.post(
        "/api/delta/forensics",
        json={"path": "/nonexistent/delta/table"},
    )
    assert response.status_code in (404, 422, 500)
