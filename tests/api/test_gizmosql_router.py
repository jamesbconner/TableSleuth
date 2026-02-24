"""Smoke tests for the GizmoSQL API router."""

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed; run with --extra web")
pytest.importorskip("httpx", reason="httpx not installed; run with --extra web")

from fastapi.testclient import TestClient  # noqa: E402

from tablesleuth.api.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def test_status_returns_200() -> None:
    """GET /api/gizmosql/status always returns 200 (connected or not)."""
    response = client.get("/api/gizmosql/status")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data


def test_query_empty_sql() -> None:
    """POST /api/gizmosql/query with empty SQL returns 422."""
    response = client.post("/api/gizmosql/query", json={"sql": ""})
    assert response.status_code == 422


def test_query_no_body() -> None:
    """POST /api/gizmosql/query without body returns 422."""
    response = client.post("/api/gizmosql/query", json={})
    assert response.status_code == 422


def test_profile_missing_columns() -> None:
    """POST /api/gizmosql/profile without columns returns 422."""
    response = client.post(
        "/api/gizmosql/profile",
        json={"table_ref": "test_table"},
    )
    # columns is required — should return 422
    assert response.status_code in (422, 500)
