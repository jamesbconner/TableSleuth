"""Smoke tests for the Parquet API router."""

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed; run with --extra web")
pytest.importorskip("httpx", reason="httpx not installed; run with --extra web")

from fastapi.testclient import TestClient  # noqa: E402

from tablesleuth.api.main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def test_analyze_missing_path() -> None:
    """POST /api/parquet/analyze with nonexistent path returns 404 or 500."""
    response = client.post(
        "/api/parquet/analyze",
        json={"path": "/nonexistent/path/that/does/not/exist"},
    )
    assert response.status_code in (404, 422, 500)


def test_analyze_no_body() -> None:
    """POST /api/parquet/analyze without required field returns 422."""
    response = client.post("/api/parquet/analyze", json={})
    assert response.status_code == 422


def test_file_info_missing() -> None:
    """POST /api/parquet/file-info with nonexistent file returns 404 or 422."""
    response = client.post(
        "/api/parquet/file-info",
        json={"path": "/nonexistent/file.parquet"},
    )
    assert response.status_code in (404, 422, 500)


def test_sample_missing() -> None:
    """POST /api/parquet/sample with nonexistent file returns non-200."""
    response = client.post(
        "/api/parquet/sample",
        json={"path": "/nonexistent/file.parquet"},
    )
    assert response.status_code != 200
