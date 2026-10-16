"""Tool facility rules.

The lease names the tool capability. Starting the process does not add to
the memory quantity. A tool result counts only after it is kept as an
embedded representation.
"""

from __future__ import annotations

KIND = "tool"


def identity(capability_id: str) -> dict[str, str]:
    """Identity is the capability id."""
    if not capability_id:
        raise ValueError("tool capability id is required")
    return {"id": capability_id}
