# -*- coding: utf-8 -*-
"""Standalone asynchronous lifecycle plugin for long-lived MCP resources.

The module is transport-agnostic and imports no sibling MCP module. Composition
is performed through an async-context-manager factory supplied by the caller.
The same task enters and exits that context, preserving anyio cancel-scope
correctness for MCP transports.
"""

from __future__ import annotations

import asyncio
import random
from contextlib import AbstractAsyncContextManager
from enum import Enum
from typing import Any, Awaitable, Callable


ResourceFactory = Callable[[], AbstractAsyncContextManager[Any]]
HealthCheck = Callable[[Any], Awaitable[None]]
StateCallback = Callable[["LifecycleState", BaseException | None], Any]


class LifecycleState(str, Enum):
    """Observable lifecycle states."""

    STOPPED = "stopped"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    PARKED = "parked"
    STOPPING = "stopping"


class MCPLifecycle:
    """Own a long-lived resource with keepalive and reconnect behavior.

    ``resource_factory`` must return a fresh asynchronous context manager for
    every call. The resource yielded by that context is exposed through
    :attr:`resource` while connected.
    """

    def __init__(
        self,
        resource_factory: ResourceFactory,
        *,
        health_check: HealthCheck | None = None,
        keepalive_interval: float = 180.0,
        initial_connect_retries: int = 3,
        max_reconnect_retries: int = 5,
        max_backoff: float = 60.0,
        parked_retry_interval: float = 300.0,
        jitter: float = 0.2,
        shutdown_timeout: float = 10.0,
        on_state_change: StateCallback | None = None,
    ) -> None:
        if not callable(resource_factory):
            raise TypeError("resource_factory must be callable.")
        if health_check is not None and not callable(health_check):
            raise TypeError("health_check must be callable.")
        if keepalive_interval < 5.0:
            raise ValueError("keepalive_interval must be at least 5 seconds.")
        if initial_connect_retries < 0 or max_reconnect_retries < 0:
            raise ValueError("retry counts must not be negative.")
        if max_backoff <= 0 or parked_retry_interval <= 0:
            raise ValueError("retry intervals must be positive.")
        if not 0.0 <= jitter < 1.0:
            raise ValueError("jitter must be in the range [0.0, 1.0).")

        self.resource_factory = resource_factory
        self.health_check = health_check or self._default_health_check
        self.keepalive_interval = keepalive_interval
        self.initial_connect_retries = initial_connect_retries
        self.max_reconnect_retries = max_reconnect_retries
        self.max_backoff = max_backoff
        self.parked_retry_interval = parked_retry_interval
        self.jitter = jitter
        self.shutdown_timeout = shutdown_timeout
        self.on_state_change = on_state_change

        self.resource: Any = None
        self.state = LifecycleState.STOPPED
        self.last_error: BaseException | None = None

        self._task: asyncio.Task[None] | None = None
        self._ready_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self._reconnect_event = asyncio.Event()
        self._initial_result_delivered = False
        self._ping_unsupported = False

    @property
    def is_connected(self) -> bool:
        """Whether the managed resource is currently available."""
        return (
            self.state is LifecycleState.CONNECTED
            and self.resource is not None
        )

    def _set_state(
        self,
        state: LifecycleState,
        error: BaseException | None = None,
    ) -> None:
        self.state = state
        self.last_error = error
        if self.on_state_change is not None:
            self.on_state_change(state, error)

    def _backoff_delay(self, base: float) -> float:
        factor = random.uniform(1.0 - self.jitter, 1.0 + self.jitter)
        return max(0.0, min(base, self.max_backoff) * factor)

    @staticmethod
    def _method_not_found(error: BaseException) -> bool:
        structured = getattr(error, "error", None)
        if getattr(structured, "code", None) == -32601:
            return True
        message = str(error).lower()
        return (
            "-32601" in message
            or "method not found" in message
            or "unknown method" in message
            or "not found: ping" in message
        )

    async def _default_health_check(self, resource: Any) -> None:
        """Use MCP ping, falling back to tools/list when ping is unsupported."""
        if not self._ping_unsupported and hasattr(resource, "send_ping"):
            try:
                await asyncio.wait_for(resource.send_ping(), timeout=30.0)
                return
            except Exception as error:
                if not self._method_not_found(error):
                    raise
                self._ping_unsupported = True

        if hasattr(resource, "list_tools"):
            await asyncio.wait_for(resource.list_tools(), timeout=30.0)
            return
        raise RuntimeError(
            "The managed resource exposes neither send_ping() nor list_tools().",
        )

    async def start(self) -> Any:
        """Start the lifecycle task and return its first connected resource."""
        if self._task is not None and not self._task.done():
            if self.is_connected:
                return self.resource
            raise RuntimeError("The lifecycle is already running.")

        self.resource = None
        self.last_error = None
        self._ready_event.clear()
        self._shutdown_event.clear()
        self._reconnect_event.clear()
        self._initial_result_delivered = False
        self._task = asyncio.create_task(
            self._run(),
            name="mcp-client-lifecycle",
        )
        await self._ready_event.wait()
        self._initial_result_delivered = True
        if self.resource is None:
            error = self.last_error
            if error is not None:
                raise error
            raise ConnectionError("MCP lifecycle stopped before connecting.")
        return self.resource

    def request_reconnect(self) -> None:
        """Request a clean transport rebuild."""
        if self._task is None or self._task.done():
            raise RuntimeError("The lifecycle is not running.")
        self._reconnect_event.set()

    async def shutdown(self) -> None:
        """Stop the lifecycle and let its owning task close the resource."""
        task = self._task
        if task is None:
            self._set_state(LifecycleState.STOPPED)
            return

        self._set_state(LifecycleState.STOPPING)
        self._shutdown_event.set()
        self._reconnect_event.set()
        if not task.done():
            try:
                await asyncio.wait_for(
                    asyncio.shield(task),
                    timeout=self.shutdown_timeout,
                )
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._task = None
        self.resource = None
        self._set_state(LifecycleState.STOPPED)

    async def _wait_for_action(self) -> str:
        """Wait for shutdown, reconnect, or the next keepalive deadline."""
        shutdown_wait = asyncio.create_task(self._shutdown_event.wait())
        reconnect_wait = asyncio.create_task(self._reconnect_event.wait())
        try:
            done, _ = await asyncio.wait(
                {shutdown_wait, reconnect_wait},
                timeout=self.keepalive_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self._shutdown_event.is_set():
                return "shutdown"
            if reconnect_wait in done:
                self._reconnect_event.clear()
                return "reconnect"
            if self.resource is None:
                raise ConnectionError("Managed MCP resource is unavailable.")
            await self.health_check(self.resource)
            return "healthy"
        finally:
            for task in (shutdown_wait, reconnect_wait):
                if not task.done():
                    task.cancel()
            await asyncio.gather(
                shutdown_wait,
                reconnect_wait,
                return_exceptions=True,
            )

    async def _park(self) -> str:
        """Wait while degraded, with explicit and periodic revival attempts."""
        shutdown_wait = asyncio.create_task(self._shutdown_event.wait())
        reconnect_wait = asyncio.create_task(self._reconnect_event.wait())
        try:
            await asyncio.wait(
                {shutdown_wait, reconnect_wait},
                timeout=self.parked_retry_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self._shutdown_event.is_set():
                return "shutdown"
            self._reconnect_event.clear()
            return "reconnect"
        finally:
            for task in (shutdown_wait, reconnect_wait):
                if not task.done():
                    task.cancel()
            await asyncio.gather(
                shutdown_wait,
                reconnect_wait,
                return_exceptions=True,
            )

    async def _run(self) -> None:
        """Connect, prove health, reconnect with backoff, and park on failure."""
        initial_failures = 0
        reconnect_failures = 0
        backoff = 1.0
        connected_once = False

        try:
            while not self._shutdown_event.is_set():
                self._set_state(LifecycleState.CONNECTING)
                try:
                    async with self.resource_factory() as resource:
                        self.resource = resource
                        self._ping_unsupported = False
                        self._set_state(LifecycleState.CONNECTED)
                        if not self._ready_event.is_set():
                            self._ready_event.set()
                        connected_once = True
                        initial_failures = 0

                        while True:
                            action = await self._wait_for_action()
                            if action == "healthy":
                                reconnect_failures = 0
                                backoff = 1.0
                                continue
                            break

                        self.resource = None
                        if action == "shutdown":
                            break
                        # A requested reconnect is a clean rebuild, not a
                        # failure and therefore consumes no retry budget.
                        if action == "reconnect":
                            continue
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    self.resource = None
                    self._set_state(LifecycleState.DEGRADED, error)
                    if not connected_once:
                        initial_failures += 1
                        exhausted = (
                            initial_failures > self.initial_connect_retries
                        )
                    else:
                        reconnect_failures += 1
                        exhausted = (
                            reconnect_failures > self.max_reconnect_retries
                        )

                    if exhausted:
                        self._set_state(LifecycleState.PARKED, error)
                        if not self._ready_event.is_set():
                            self._ready_event.set()
                        action = await self._park()
                        if action == "shutdown":
                            break
                        initial_failures = 0
                        reconnect_failures = 0
                        backoff = 1.0
                        continue

                    await asyncio.sleep(self._backoff_delay(backoff))
                    backoff = min(backoff * 2.0, self.max_backoff)
        finally:
            self.resource = None
            if not self._ready_event.is_set():
                self._ready_event.set()
            self._set_state(LifecycleState.STOPPED)
