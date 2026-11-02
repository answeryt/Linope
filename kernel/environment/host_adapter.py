"""Ask the host to enforce process limits.

Agent OS does not page physical memory. ``max_memory_bytes`` and the runtime
limit are host mechanisms. When the host cannot apply them, this module reports
that and leaves the process running.
"""

from __future__ import annotations

import sys
from typing import Any

from kernel.environment.policy import HostExecutionPolicy


def host_limit_request(policy: HostExecutionPolicy | None) -> dict[str, Any]:
    """The limits Agent OS hands to the host. This is not a page table."""

    chosen = policy or HostExecutionPolicy()
    return {
        "enforced_by": "host",
        "max_memory_bytes": chosen.max_memory_bytes,
        "max_runtime_seconds": chosen.max_runtime_seconds,
    }


def apply_host_limits(process: Any, policy: HostExecutionPolicy | None = None) -> dict[str, Any]:
    """Best-effort host enforcement. A missing limit is a no-op."""

    request = host_limit_request(policy)
    request["applied"] = False
    if request["max_memory_bytes"] is None and request["max_runtime_seconds"] is None:
        return request
    pid = getattr(process, "pid", None)
    if not pid:
        request["reason"] = "no process"
        return request
    if sys.platform == "win32":
        request["reason"] = "windows job is left to the host supervisor"
        return request
    request["applied"] = _posix_memory(int(pid), request["max_memory_bytes"])
    if not request["applied"]:
        request["reason"] = "host did not apply a memory limit"
    return request


def _posix_memory(pid: int, max_bytes: int | None) -> bool:
    if max_bytes is None or pid <= 0:
        return False
    try:
        import resource

        resource.prlimit(pid, resource.RLIMIT_AS, (int(max_bytes), int(max_bytes)))
    except (AttributeError, OSError, ValueError):
        return False
    return True
