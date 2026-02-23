"""Tests for TOML escaping in config router."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import tomllib

from tablesleuth.api.routers.config import _write_toml
from tablesleuth.config import AppConfig, CatalogConfig, GizmoConfig


def test_write_toml_escapes_quotes() -> None:
    """Test that double quotes in values are properly escaped."""
    cfg = AppConfig(
        catalog=CatalogConfig(default="test_catalog"),
        gizmosql=GizmoConfig(
            uri="grpc://localhost:31337",
            username='user"with"quotes',
            password='pass"word',
            tls_skip_verify=False,
        ),
    )

    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.toml"
        _write_toml(path, cfg)

        # Verify the file can be parsed back
        content = path.read_text()
        parsed = tomllib.loads(content)

        assert parsed["gizmosql"]["username"] == 'user"with"quotes'
        assert parsed["gizmosql"]["password"] == 'pass"word'


def test_write_toml_escapes_backslashes() -> None:
    """Test that backslashes in values are properly escaped."""
    cfg = AppConfig(
        catalog=CatalogConfig(default="test_catalog"),
        gizmosql=GizmoConfig(
            uri="grpc://localhost:31337",
            username=r"domain\user",
            password=r"pass\word",
            tls_skip_verify=False,
        ),
    )

    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.toml"
        _write_toml(path, cfg)

        # Verify the file can be parsed back
        content = path.read_text()
        parsed = tomllib.loads(content)

        assert parsed["gizmosql"]["username"] == r"domain\user"
        assert parsed["gizmosql"]["password"] == r"pass\word"


def test_write_toml_escapes_combined_special_chars() -> None:
    """Test that combinations of special characters are properly escaped."""
    cfg = AppConfig(
        catalog=CatalogConfig(default="test_catalog"),
        gizmosql=GizmoConfig(
            uri="grpc://localhost:31337",
            username=r'user\"with\both"',
            password=r'complex\"pass"word\\',
            tls_skip_verify=True,
        ),
    )

    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.toml"
        _write_toml(path, cfg)

        # Verify the file can be parsed back
        content = path.read_text()
        parsed = tomllib.loads(content)

        assert parsed["gizmosql"]["username"] == r'user\"with\both"'
        assert parsed["gizmosql"]["password"] == r'complex\"pass"word\\'
        assert parsed["gizmosql"]["tls_skip_verify"] is True


def test_write_toml_normal_values() -> None:
    """Test that normal values without special characters work correctly."""
    cfg = AppConfig(
        catalog=CatalogConfig(default="my_catalog"),
        gizmosql=GizmoConfig(
            uri="grpc+tls://example.com:31337",
            username="normal_user",
            password="normal_password",
            tls_skip_verify=False,
        ),
    )

    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "test.toml"
        _write_toml(path, cfg)

        # Verify the file can be parsed back
        content = path.read_text()
        parsed = tomllib.loads(content)

        assert parsed["catalog"]["default"] == "my_catalog"
        assert parsed["gizmosql"]["uri"] == "grpc+tls://example.com:31337"
        assert parsed["gizmosql"]["username"] == "normal_user"
        assert parsed["gizmosql"]["password"] == "normal_password"
        assert parsed["gizmosql"]["tls_skip_verify"] is False
