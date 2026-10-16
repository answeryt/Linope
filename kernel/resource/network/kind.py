"""Network facility rules.

The lease records which outside hosts are listed. An empty list does not
by itself close an existing exit.
"""

from __future__ import annotations

KIND = "network"


def hosts(names: tuple[str, ...]) -> tuple[str, ...]:
    """Host names kept on the network lease. Blank names are dropped."""
    return tuple(name.strip() for name in names if name.strip())


def identity(names: tuple[str, ...]) -> dict[str, str]:
    """Identity is the sorted host list."""
    listed = tuple(sorted(set(hosts(names))))
    if not listed:
        raise ValueError("network hosts are required")
    return {"hosts": ",".join(listed)}
