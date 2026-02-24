"""Tests for web utilities."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tablesleuth.utils.web_utils import resolve_web_dir


def test_resolve_web_dir_env_var() -> None:
    """Test that TABLESLEUTH_WEB_UI_DIR env var takes priority."""
    with TemporaryDirectory() as tmpdir:
        web_dir = Path(tmpdir) / "web"
        web_dir.mkdir()
        (web_dir / "index.html").write_text("<html></html>")

        with patch.dict(os.environ, {"TABLESLEUTH_WEB_UI_DIR": str(web_dir)}):
            result = resolve_web_dir()
            assert result == web_dir


def test_resolve_web_dir_env_var_nonexistent() -> None:
    """Test that nonexistent env var path is skipped."""
    with patch.dict(os.environ, {"TABLESLEUTH_WEB_UI_DIR": "/nonexistent/path"}):
        # Should fall through to other resolution methods
        result = resolve_web_dir()
        # Result depends on whether package or dev build exists
        assert result is None or result.exists()


def test_resolve_web_dir_no_env_var() -> None:
    """Test resolution without env var set."""
    with patch.dict(os.environ, {}, clear=True):
        result = resolve_web_dir()
        # Result depends on whether package or dev build exists
        # Just verify it returns a Path or None
        assert result is None or isinstance(result, Path)


def test_resolve_web_dir_returns_none_when_not_found() -> None:
    """Test that None is returned when no web directory is found."""
    # Set env var to nonexistent path and ensure package/dev paths don't exist
    with patch.dict(os.environ, {"TABLESLEUTH_WEB_UI_DIR": "/absolutely/nonexistent/path"}):
        # Mock Path.is_dir to always return False
        with patch("tablesleuth.utils.web_utils.Path.is_dir", return_value=False):
            result = resolve_web_dir()
            assert result is None
