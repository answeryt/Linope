"""Host-side execution policy attached to a capability process room."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HostExecutionPolicy:
    """Limits enforced by the host, not by Agent Resource semantics."""

    startup_timeout_seconds: float = 10.0
    graceful_shutdown_timeout_seconds: float = 5.0
    max_runtime_seconds: float | None = None
    max_memory_bytes: int | None = None
    heartbeat_interval_seconds: float | None = None
    heartbeat_timeout_seconds: float = 2.0
    max_restarts: int = 0
    restart_window_seconds: float = 60.0

    def __post_init__(self) -> None:
        for name in (
            "startup_timeout_seconds",
            "graceful_shutdown_timeout_seconds",
            "max_runtime_seconds",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.max_memory_bytes is not None and self.max_memory_bytes < 0:
            raise ValueError("max_memory_bytes cannot be negative")
        if (
            self.heartbeat_interval_seconds is not None
            and self.heartbeat_interval_seconds < 0
        ):
            raise ValueError("heartbeat_interval_seconds cannot be negative")
        if self.heartbeat_timeout_seconds < 0:
            raise ValueError("heartbeat_timeout_seconds cannot be negative")
        if self.max_restarts < 0:
            raise ValueError("max_restarts cannot be negative")
        if self.restart_window_seconds < 0:
            raise ValueError("restart_window_seconds cannot be negative")

    def payload(self) -> dict[str, Any]:
        return {
            "startup_timeout_seconds": self.startup_timeout_seconds,
            "graceful_shutdown_timeout_seconds": (
                self.graceful_shutdown_timeout_seconds
            ),
            "max_runtime_seconds": self.max_runtime_seconds,
            "max_memory_bytes": self.max_memory_bytes,
            "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
            "heartbeat_timeout_seconds": self.heartbeat_timeout_seconds,
            "max_restarts": self.max_restarts,
            "restart_window_seconds": self.restart_window_seconds,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "HostExecutionPolicy":
        raw = dict(payload or {})
        return cls(
            startup_timeout_seconds=float(raw.get("startup_timeout_seconds", 10.0)),
            graceful_shutdown_timeout_seconds=float(
                raw.get("graceful_shutdown_timeout_seconds", 5.0)
            ),
            max_runtime_seconds=_optional_float(raw, "max_runtime_seconds"),
            max_memory_bytes=_optional_int(raw, "max_memory_bytes"),
            heartbeat_interval_seconds=_optional_float(
                raw, "heartbeat_interval_seconds"
            ),
            heartbeat_timeout_seconds=float(raw.get("heartbeat_timeout_seconds", 2.0)),
            max_restarts=int(raw.get("max_restarts", 0)),
            restart_window_seconds=float(raw.get("restart_window_seconds", 60.0)),
        )


def _optional_float(raw: dict[str, Any], name: str) -> float | None:
    if name not in raw or raw[name] is None:
        return None
    return float(raw[name])


def _optional_int(raw: dict[str, Any], name: str) -> int | None:
    if name not in raw or raw[name] is None:
        return None
    return int(raw[name])
