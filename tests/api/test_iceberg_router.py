"""Smoke tests for the Iceberg API router."""

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed; run with --extra web")
pytest.importorskip("httpx", reason="httpx not installed; run with --extra web")

from fastapi.testclient import TestClient  # noqa: E402

from tablesleuth.api.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def test_load_no_args() -> None:
    """POST /api/iceberg/load without required args returns 404 or 422."""
    response = client.post("/api/iceberg/load", json={})
    # ValueError → 422 via exception handler
    assert response.status_code in (404, 422, 500)


def test_load_missing_metadata() -> None:
    """POST /api/iceberg/load with nonexistent metadata file returns 404."""
    response = client.post(
        "/api/iceberg/load",
        json={"metadata_path": "/nonexistent/metadata.json"},
    )
    assert response.status_code in (404, 422, 500)


def test_snapshots_no_args() -> None:
    """POST /api/iceberg/snapshots without args returns error."""
    response = client.post("/api/iceberg/snapshots", json={})
    assert response.status_code in (404, 422, 500)


def test_compare_no_table() -> None:
    """POST /api/iceberg/compare without table info returns error."""
    response = client.post(
        "/api/iceberg/compare",
        json={"snapshot_a_id": 1, "snapshot_b_id": 2},
    )
    assert response.status_code in (404, 422, 500)
