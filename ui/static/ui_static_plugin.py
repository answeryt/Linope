# -*- coding: utf-8 -*-
"""SPA dist fallback: traversal is 403, misses serve index.html with HTTP 200."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import unquote


PLUGIN_NAME = "ui_static"
PLUGIN_VERSION = "1.0"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".json": "application/json",
    ".map": "application/json",
    ".webmanifest": "application/manifest+json",
}

_MISSING_DIST = (
    "ui: frontend dist not built; run the frontend build under ui/frontend first"
)


def resolve_dist_index(frontend_root: str | None = None) -> str:
    """Dist location is workspace knowledge of this UI, never a user flag."""
    root = Path(frontend_root) if frontend_root else Path(__file__).resolve().parents[1] / "frontend"
    path = root / "dist" / "index.html"
    if not path.is_file():
        raise FileNotFoundError(_MISSING_DIST)
    return str(path)


def serve_static(
    pathname: str,
    *,
    dist_root: str,
    dist_index: str,
    render_index: Callable[[], str],
) -> dict[str, Any]:
    root = Path(dist_root).resolve()
    index = Path(dist_index).resolve()
    relative = unquote_path(pathname)
    target = (root / relative).resolve() if relative else root
    if target != root and root not in target.parents:
        return {"status": 403, "headers": {}, "body": b""}
    if target == root or target == index:
        return _index_response(render_index)
    try:
        if target.is_dir() or not target.is_file():
            return _index_response(render_index)
        body = target.read_bytes()
        suffix = target.suffix.lower()
        return {
            "status": 200,
            "headers": {"content-type": MIME.get(suffix, "application/octet-stream")},
            "body": body,
        }
    except OSError:
        return _index_response(render_index)


def mount_static(
    *,
    register_fallback: Callable[[Callable[[dict[str, str]], dict[str, Any]]], None],
    apply_index_taps: Callable[[str], str],
    dist_index: str,
) -> None:
    index = Path(dist_index)
    dist_root = str(index.parent)

    def render_index() -> str:
        return apply_index_taps(index.read_text(encoding="utf-8"))

    def fallback(request: dict[str, str]) -> dict[str, Any]:
        method = str(request.get("method") or "GET").upper()
        if method not in ("GET", "HEAD"):
            return {"status": 405, "headers": {}, "body": b""}
        return serve_static(
            str(request.get("path") or "/"),
            dist_root=dist_root,
            dist_index=str(index),
            render_index=render_index,
        )

    register_fallback(fallback)


def unquote_path(pathname: str) -> str:
    text = unquote(pathname).replace("\\", "/")
    if text.startswith("/"):
        text = text[1:]
    return text


def _index_response(render_index: Callable[[], str]) -> dict[str, Any]:
    body = render_index().encode("utf-8")
    return {
        "status": 200,
        "headers": {"content-type": MIME[".html"]},
        "body": body,
    }
