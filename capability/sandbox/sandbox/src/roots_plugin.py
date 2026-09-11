# -*- coding: utf-8 -*-
"""Canonical writable roots for one sandbox file-effect policy.

workspace-write means the workspace plus platform temp areas. Host injects
canonical_path / writable_roots into Seatbelt and fs fences so those grants
cannot drift. This file never imports sibling plugins.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from typing import Any


PLUGIN_NAME = "sandbox_roots"
PLUGIN_VERSION = "1.0"

READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
DANGER_FULL_ACCESS = "danger-full-access"

HOST_TMP = "/tmp"


def canonical_path(path: str) -> str:
    """Resolve *path* the way enforcement compares it (symlinks followed).

    A missing or unreadable root is returned as spelled: inventing a fallback
    would grant a path the caller never named.
    """
    try:
        return os.path.realpath(path, strict=True)
    except (OSError, ValueError):
        return path


def writable_roots(policy: Mapping[str, Any]) -> list[str]:
    """Writable allow-list for one call. Empty unless mode is workspace-write."""
    mode = str(policy.get("mode") or "")
    if mode != WORKSPACE_WRITE:
        return []
    workspace = str(
        policy.get("workspace_root") or policy.get("workspaceRoot") or ""
    )
    roots = [workspace, HOST_TMP, tempfile.gettempdir()]
    return list(dict.fromkeys(canonical_path(item) for item in roots))
