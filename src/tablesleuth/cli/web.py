"""Launch the TableSleuth web UI (FastAPI + Next.js)."""

from __future__ import annotations

import logging
import os
import threading
import time
import webbrowser
from pathlib import Path

import click

logger = logging.getLogger(__name__)


def _resolve_web_dir() -> Path | None:
    """Resolve the web UI directory in priority order.

    Priority:
    1. TABLESLEUTH_WEB_UI_DIR env var
    2. Installed package: <package_root>/web
    3. Dev build: <repo_root>/web-ui/out

    Returns:
        Path to web directory if it exists, else None.
    """
    # 1. Env var override
    env_dir = os.getenv("TABLESLEUTH_WEB_UI_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p

    # 2. Installed package location (bundled in wheel)
    pkg_web = Path(__file__).parent.parent / "web"
    if pkg_web.is_dir() and (pkg_web / "index.html").exists():
        return pkg_web

    # 3. Dev build output (repo checkout)
    dev_web = Path(__file__).parent.parent.parent.parent / "web-ui" / "out"
    if dev_web.is_dir() and (dev_web / "index.html").exists():
        return dev_web

    return None


@click.command("web")
@click.option("--host", default="localhost", show_default=True, help="Host to bind the server to.")
@click.option("--port", default=8000, show_default=True, type=int, help="Port to listen on.")
@click.option("--no-browser", is_flag=True, default=False, help="Do not open browser automatically.")
@click.option(
    "--log-level",
    default="warning",
    show_default=True,
    type=click.Choice(["debug", "info", "warning", "error"], case_sensitive=False),
    help="Uvicorn log level.",
)
def web(host: str, port: int, no_browser: bool, log_level: str) -> None:
    """Launch the TableSleuth web UI.

    Starts a FastAPI server and optionally opens the browser. The frontend is
    served from the bundled Next.js static export (or the dev build at web-ui/out).

    To install web dependencies:
        pip install tablesleuth[web]

    To rebuild the frontend (developers):
        make build-release
    """
    # Check uvicorn is importable
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        raise click.ClickException(
            "uvicorn is not installed. Install web dependencies with:\n"
            "    pip install tablesleuth[web]\n"
            "or:\n"
            "    uv sync --extra web"
        )

    # Resolve web UI directory
    web_dir = _resolve_web_dir()
    if web_dir is None:
        click.echo(
            "Warning: Web UI static files not found. The API will start but no UI will be served.\n"
            "  - For production: pip install tablesleuth[web] (includes pre-built UI)\n"
            "  - For development: run 'make build-release' first, or 'make dev-web' separately.",
            err=True,
        )
    else:
        click.echo(f"Serving web UI from: {web_dir}")

    url = f"http://{host}:{port}"
    click.echo(f"Starting TableSleuth web UI at {url}")

    # Open browser after 1.2s delay in daemon thread
    if not no_browser:

        def _open_browser() -> None:
            time.sleep(1.2)
            webbrowser.open(url)

        t = threading.Thread(target=_open_browser, daemon=True)
        t.start()

    # Launch uvicorn
    import uvicorn

    uvicorn.run(
        "tablesleuth.api.main:app",
        host=host,
        port=port,
        log_level=log_level.lower(),
        reload=False,
    )
