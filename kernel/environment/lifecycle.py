"""How long the process may run, and when it is asked to stop."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from typing import Any

from kernel.environment.policy import HostExecutionPolicy


@dataclass(frozen=True)
class LifecycleDoor:
    """Wall-clock stop lives here. Startup and shutdown waits stay on the supervisor."""

    startup_timeout_seconds: float = 10.0
    graceful_shutdown_timeout_seconds: float = 5.0
    max_runtime_seconds: float | None = None
    max_memory_bytes: int | None = None
    heartbeat_interval_seconds: float | None = None
    heartbeat_timeout_seconds: float = 2.0
    max_restarts: int = 0
    restart_window_seconds: float = 60.0

    def deadline_reached(self, started_at: float, now: float | None = None) -> bool:
        if self.max_runtime_seconds is None:
            return False
        current = time.monotonic() if now is None else now
        return current - started_at >= self.max_runtime_seconds

    def ask_stop(
        self,
        store: Any,
        process_id: str,
        started_at: float,
        now: float | None = None,
    ) -> bool:
        """When the wall clock is up, ask the process to stop."""
        if not self.deadline_reached(started_at, now):
            return False
        store.set_desired(process_id, "stop")
        return True

    def memory_over_limit(self, used_bytes: int | None) -> bool:
        """Compare a sample. This does not apply a cgroup or kill the process."""
        if self.max_memory_bytes is None or used_bytes is None:
            return False
        return used_bytes > self.max_memory_bytes

    def heartbeat_late(self, last_beat: float | None, now: float | None = None) -> bool:
        """True when a heartbeat was required and did not arrive in time."""
        if self.heartbeat_interval_seconds is None:
            return False
        if last_beat is None:
            return True
        current = time.monotonic() if now is None else now
        return current - last_beat > self.heartbeat_timeout_seconds

    def payload(self) -> dict[str, Any]:
        return {
            "startup_timeout_seconds": self.startup_timeout_seconds,
            "graceful_shutdown_timeout_seconds": self.graceful_shutdown_timeout_seconds,
            "max_runtime_seconds": self.max_runtime_seconds,
            "max_memory_bytes": self.max_memory_bytes,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "heartbeat_timeout_seconds": self.heartbeat_timeout_seconds,
            "max_restarts": self.max_restarts,
            "restart_window_seconds": self.restart_window_seconds,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "LifecycleDoor":
        return cls.from_policy(HostExecutionPolicy.from_payload(payload))

    @classmethod
    def from_policy(cls, policy: HostExecutionPolicy) -> "LifecycleDoor":
        return cls(
            startup_timeout_seconds=policy.startup_timeout_seconds,
            graceful_shutdown_timeout_seconds=policy.graceful_shutdown_timeout_seconds,
            max_runtime_seconds=policy.max_runtime_seconds,
            max_memory_bytes=policy.max_memory_bytes,
            heartbeat_interval_seconds=policy.heartbeat_interval_seconds,
            heartbeat_timeout_seconds=policy.heartbeat_timeout_seconds,
            max_restarts=policy.max_restarts,
            restart_window_seconds=policy.restart_window_seconds,
        )


def sample_memory_bytes() -> int | None:
    """Best-effort working set. None means this host did not report a number."""
    try:
        if os.name == "nt":
            return _windows_working_set()
        import resource

        rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        if sys.platform == "darwin":
            return rss
        return rss * 1024
    except Exception:
        return None


def _windows_working_set() -> int | None:
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    ok = ctypes.windll.psapi.GetProcessMemoryInfo(
        handle, ctypes.byref(counters), counters.cb
    )
    if not ok:
        return None
    return int(counters.WorkingSetSize)
