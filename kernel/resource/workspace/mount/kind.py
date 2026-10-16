"""Workspace identity is the project root shared by file-touching peers."""

from __future__ import annotations

import os

KIND = "workspace"


def identity(root: str) -> dict[str, str]:
    """Identity is the project root, so named peers can share one view."""
    text = str(root or "").strip()
    if not text:
        raise ValueError("workspace root is required")
    return {"root": os.path.normpath(os.path.expanduser(text))}


def root_from(changes, fallback: str) -> str:
    """Read a workspace root from change clauses, otherwise use fallback."""
    for topic, raw in changes or ():
        if topic in {"workspace", "workspace_root", "cwd"} and str(raw).strip():
            return str(raw)
    return fallback
