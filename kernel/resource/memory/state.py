"""Open a memory resource. The body lives in a MemoryStore, not in this dict."""

from __future__ import annotations

from typing import Any


def open_state(identity: dict[str, Any]) -> dict[str, Any]:
    """A handle for the scope. Rows are not copied into the resource entity."""

    return {
        "scope": str(identity.get("scope") or ""),
        "backend": str(identity.get("backend") or ""),
    }
