"""Communication facility rules.

Delivery stays in ``kernel.communication``. This record is the
channel name kept beside the resource lease.
"""

from __future__ import annotations

KIND = "communication"


def channel(name: str) -> str:
    """The channel name on the resource side. Delivery is elsewhere."""
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("通道名字不能是空白")
    return cleaned
