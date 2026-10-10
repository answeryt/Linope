# -*- coding: utf-8 -*-
"""Standalone MCP retry, timeout, circuit-breaker, and process-guard plugin."""

from __future__ import annotations

import asyncio
import errno
import inspect
import os
import random
import signal
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable


PLUGIN_NAME = "mcp_resilience"
PLUGIN_VERSION = "1.0"

_SESSION_MARKERS = (
    "invalid or expired session",
    "expired session",
    "session expired",
    "session not found",
    "unknown session",
    "session terminated",
    "closedresourceerror",
    "closed resource",
    "transport is closed",
    "connection closed",
    "broken pipe",
    "end of file",
)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(ConnectionError):
    """Raised while a server circuit is cooling down."""


class FailureKind(str, Enum):
    AUTH = "auth"
    SESSION_EXPIRED = "session_expired"
    PERMANENT = "permanent"
    TRANSIENT = "transient"
    INTERRUPTED = "interrupted"


@dataclass
class CircuitBreaker:
    """Closed/open/half-open breaker for one MCP server."""

    threshold: int = 3
    cooldown: float = 60.0
    failures: int = 0
    opened_at: float | None = None
    probe_in_flight: bool = False

    @property
    def state(self) -> CircuitState:
        if self.failures < self.threshold:
            return CircuitState.CLOSED
        if self.opened_at is None:
            return CircuitState.OPEN
        if time.monotonic() - self.opened_at >= self.cooldown:
            return CircuitState.HALF_OPEN
        return CircuitState.OPEN

    def before_call(self) -> None:
        state = self.state
        if state is CircuitState.OPEN:
            remaining = max(
                0.0,
                self.cooldown - (time.monotonic() - (self.opened_at or 0.0)),
            )
            raise CircuitOpenError(
                f"MCP circuit is open; retry in {remaining:.1f}s.",
            )
        if state is CircuitState.HALF_OPEN:
            if self.probe_in_flight:
                raise CircuitOpenError("MCP circuit half-open probe is in flight.")
            self.probe_in_flight = True

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None
        self.probe_in_flight = False

    def failure(self) -> None:
        self.failures += 1
        self.probe_in_flight = False
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


def exception_nodes(error: BaseException, limit: int = 10_000) -> list[BaseException]:
    """Flatten groups and chained errors with cycle and size protection."""
    stack: list[BaseException | None] = [error]
    nodes: list[BaseException] = []
    seen: set[int] = set()
    while stack and len(nodes) < limit:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        nodes.append(current)
        stack.extend(getattr(current, "exceptions", ()) or ())
        stack.append(getattr(current, "__cause__", None))
        stack.append(getattr(current, "__context__", None))
    return nodes


def classify_failure(error: BaseException) -> FailureKind:
    """Classify retryability without depending on one SDK version."""
    nodes = exception_nodes(error)
    if any(isinstance(node, (InterruptedError, asyncio.CancelledError)) for node in nodes):
        return FailureKind.INTERRUPTED
    for node in nodes:
        status = getattr(getattr(node, "response", None), "status_code", None)
        name = type(node).__name__.lower()
        message = str(node).lower()
        if status in {401, 403} or "unauthorized" in name or "oauth" in name:
            return FailureKind.AUTH
        if any(marker in message or marker in name for marker in _SESSION_MARKERS):
            return FailureKind.SESSION_EXPIRED
        if isinstance(node, FileNotFoundError):
            return FailureKind.PERMANENT
        if isinstance(node, OSError) and getattr(node, "errno", None) == errno.ENOENT:
            return FailureKind.PERMANENT
    return FailureKind.TRANSIENT


async def _await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class MCPResiliencePlugin:
    """Execute MCP RPCs with serialization, recovery, and bounded retries."""

    def __init__(
        self,
        *,
        timeout: float = 60.0,
        max_retries: int = 2,
        base_backoff: float = 1.0,
        max_backoff: float = 30.0,
        jitter: float = 0.2,
        breaker_threshold: int = 3,
        breaker_cooldown: float = 60.0,
        serialize_calls: bool = True,
    ) -> None:
        if timeout <= 0 or base_backoff <= 0 or max_backoff <= 0:
            raise ValueError("timeouts and backoff values must be positive.")
        if max_retries < 0 or breaker_threshold < 1:
            raise ValueError("retry count and breaker threshold are invalid.")
        if not 0 <= jitter < 1:
            raise ValueError("jitter must be in [0, 1).")
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.jitter = jitter
        self.breaker_threshold = breaker_threshold
        self.breaker_cooldown = breaker_cooldown
        self.serialize_calls = serialize_calls
        self._breakers: dict[str, CircuitBreaker] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def breaker(self, server_name: str) -> CircuitBreaker:
        return self._breakers.setdefault(
            server_name,
            CircuitBreaker(self.breaker_threshold, self.breaker_cooldown),
        )

    def reset(self, server_name: str) -> None:
        """Close the server circuit after a proven healthy operation."""
        self.breaker(server_name).success()

    async def call(
        self,
        server_name: str,
        operation: Callable[[], Any | Awaitable[Any]],
        *,
        reconnect: Callable[[], Any | Awaitable[Any]] | None = None,
        refresh_auth: Callable[[], Any | Awaitable[Any]] | None = None,
        retry_if: Callable[[BaseException], bool] | None = None,
    ) -> Any:
        """Run one RPC; auth/session recovery gets at most one rebuilt retry."""
        breaker = self.breaker(server_name)
        breaker.before_call()
        lock = self._locks.setdefault(server_name, asyncio.Lock())

        async def execute() -> Any:
            if inspect.iscoroutinefunction(operation):
                pending = operation()
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(operation),
                    timeout=self.timeout,
                )
                if not inspect.isawaitable(result):
                    return result
                pending = result
            return await asyncio.wait_for(
                _await(pending),
                timeout=self.timeout,
            )

        async def guarded() -> Any:
            delay = self.base_backoff
            recovered_auth = False
            recovered_session = False
            for attempt in range(self.max_retries + 1):
                try:
                    result = await execute()
                    breaker.success()
                    return result
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    kind = classify_failure(error)
                    if kind is FailureKind.INTERRUPTED:
                        raise
                    if (
                        kind is FailureKind.AUTH
                        and not recovered_auth
                        and refresh_auth is not None
                        and reconnect is not None
                    ):
                        recovered_auth = True
                        if await _await(refresh_auth()):
                            await _await(reconnect())
                            continue
                    if (
                        kind is FailureKind.SESSION_EXPIRED
                        and not recovered_session
                        and reconnect is not None
                    ):
                        recovered_session = True
                        await _await(reconnect())
                        continue
                    allowed = (
                        retry_if(error)
                        if retry_if is not None
                        else kind is FailureKind.TRANSIENT
                    )
                    if not allowed or attempt >= self.max_retries:
                        breaker.failure()
                        raise
                    spread = random.uniform(1.0 - self.jitter, 1.0 + self.jitter)
                    await asyncio.sleep(min(delay, self.max_backoff) * spread)
                    delay = min(delay * 2.0, self.max_backoff)
            raise RuntimeError("Unreachable MCP retry state.")

        if not self.serialize_calls:
            return await guarded()
        async with lock:
            return await guarded()


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    process_group: int | None = None


class MCPProcessGuard:
    """Track only explicitly registered MCP children and terminate on shutdown."""

    def __init__(self, *, graceful_timeout: float = 5.0) -> None:
        if graceful_timeout < 0:
            raise ValueError("graceful_timeout must not be negative.")
        self.graceful_timeout = graceful_timeout
        self._records: dict[int, ProcessRecord] = {}

    def register(self, pid: int, process_group: int | None = None) -> None:
        if not isinstance(pid, int) or pid <= 0:
            raise ValueError("pid must be a positive integer.")
        self._records[pid] = ProcessRecord(pid, process_group)

    def unregister(self, pid: int) -> None:
        self._records.pop(pid, None)

    @staticmethod
    def watchdog_command(command: str, args: list[str], watchdog: str) -> tuple[str, list[str]]:
        """Wrap a command with an explicit parent-death watchdog executable."""
        return watchdog, ["--ppid", str(os.getpid()), "--", command, *args]

    def _alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def terminate(self, pid: int) -> bool:
        """Terminate one registered process tree, then escalate if necessary."""
        record = self._records.get(pid)
        if record is None:
            return False
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T"],
                    check=False,
                    capture_output=True,
                    timeout=max(1.0, self.graceful_timeout),
                )
            elif record.process_group is not None:
                os.killpg(record.process_group, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except (OSError, subprocess.SubprocessError):
            pass

        deadline = time.monotonic() + self.graceful_timeout
        while self._alive(pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        if self._alive(pid):
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        check=False,
                        capture_output=True,
                        timeout=5.0,
                    )
                elif record.process_group is not None:
                    os.killpg(record.process_group, signal.SIGKILL)
                else:
                    os.kill(pid, signal.SIGKILL)
            except (OSError, subprocess.SubprocessError):
                return False
        self.unregister(pid)
        return not self._alive(pid)

    def cleanup(self) -> dict[int, bool]:
        """Terminate every registered MCP child without scanning unrelated PIDs."""
        return {pid: self.terminate(pid) for pid in tuple(self._records)}

def capability_profile(capability_id, changes):
    """Tell the process this tool needs a tool resource."""
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
        ),
    )

