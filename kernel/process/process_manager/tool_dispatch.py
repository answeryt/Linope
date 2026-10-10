"""Build structured tool requests for existing capability processes."""

from __future__ import annotations

from typing import Any


def tool_capability(name: str) -> str:
    value = str(name).strip()
    return value if value.startswith("tools.") else f"tools.{value}"


def tool_request(name: str, arguments: Any) -> dict[str, Any]:
    """Return the existing process-adapter message shape for one tool call."""
    del name
    return {
        "operation": "load",
        "kind": "tool",
        "body": arguments if isinstance(arguments, dict) else {},
    }
