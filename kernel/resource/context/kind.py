"""Context facility rules.

The lease names a compression capability. It is not the representation body
and it is not the memory quantity.
"""

from __future__ import annotations

KIND = "context"


def identity(capability_id: str) -> dict[str, str]:
    """Identity is the capability id."""
    if not capability_id:
        raise ValueError("context capability id is required")
    return {"id": capability_id}
