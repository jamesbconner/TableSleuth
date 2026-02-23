"""Web UI utilities."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_web_dir() -> Path | None:
    """Resolve the web UI directory in priority order.

    Priority:
    1. TABLESLEUTH_WEB_UI_DIR env var
    2. Installed package: <package_root>/web
    3. Dev build: <repo_root>/web-ui/out

    Returns:
        Path to web directory if found, else None.
    """
    # 1. Env var override
    env_dir = os.getenv("TABLESLEUTH_WEB_UI_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p

    # 2. Installed package location
    # Navigate from utils/web_utils.py -> utils -> tablesleuth -> web
    pkg_web = Path(__file__).parent.parent / "web"
    if pkg_web.is_dir() and (pkg_web / "index.html").exists():
        return pkg_web

    # 3. Dev build output (repo checkout)
    # Navigate from utils/web_utils.py -> utils -> tablesleuth -> src -> repo_root -> web-ui/out
    dev_web = Path(__file__).parent.parent.parent.parent / "web-ui" / "out"
    if dev_web.is_dir() and (dev_web / "index.html").exists():
        return dev_web

    return None
