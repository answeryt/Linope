# -*- coding: utf-8 -*-
"""Standalone multi-server MCP host-management plugin.

Connections are supplied as asynchronous context-manager factories.  Every
factory is entered and exited by the same owner task, preserving anyio
cancel-scope correctness without importing a transport or lifecycle sibling.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping


PLUGIN_NAME = "mcp_host_manager"
PLUGIN_VERSION = "1.0"

ResourceFactory = Callable[[], Any]
DiscoverHandler = Callable[[Any], Any | Awaitable[Any]]
StateHandler = Callable[[dict[str, Any]], Any | Awaitable[Any]]


class ServerState(str, Enum):
    CONFIGURED = "configured"
    DISABLED = "disabled"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    PARKED = "parked"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class ServerSpec:
    """Host-neutral description of one managed MCP server."""

    name: str
    resource_factory: ResourceFactory
    enabled: bool = True
    discover: DiscoverHandler | None = None
    connect_timeout: float = 60.0
    keepalive_interval: float = 180.0
    max_retries: int = 5
    max_backoff: float = 60.0
    parked_retry_interval: float = 300.0
    metadata: dict[str, Any] = field(default_factory=dict)


class _ServerRuntime:
    def __init__(
        self,
        spec: ServerSpec,
        on_state: StateHandler | None,
    ) -> None:
        self.spec = spec
        self.on_state = on_state
        self.state = ServerState.CONFIGURED if spec.enabled else ServerState.DISABLED
        self.resource: Any = None
        self.discovered: Any = None
        self.error: BaseException | None = None
        self.connected_at: float | None = None
        self.generation = 0
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._shutdown = asyncio.Event()
        self._reconnect = asyncio.Event()
        self._rpc_lock = asyncio.Lock()

    async def _set_state(
        self,
        state: ServerState,
        error: BaseException | None = None,
    ) -> None:
        self.state = state
        self.error = error
        if self.on_state is not None:
            event = {
                "server": self.spec.name,
                "state": state.value,
                "error": error,
                "generation": self.generation,
            }
            result = self.on_state(event)
            if inspect.isawaitable(result):
                await result

    async def start(self) -> Any:
        if not self.spec.enabled:
            await self._set_state(ServerState.DISABLED)
            return None
        if self._task is not None and not self._task.done():
            if self.resource is not None:
                return self.resource
            await asyncio.wait_for(
                self._ready.wait(),
                timeout=self.spec.connect_timeout,
            )
            if self.resource is None:
                raise self.error or ConnectionError(
                    f"MCP server {self.spec.name!r} did not connect.",
                )
            return self.resource

        self._ready.clear()
        self._shutdown.clear()
        self._reconnect.clear()
        self._task = asyncio.create_task(
            self._run(),
            name=f"mcp-host-{self.spec.name}",
        )
        await asyncio.wait_for(
            self._ready.wait(),
            timeout=self.spec.connect_timeout,
        )
        if self.resource is None:
            raise self.error or ConnectionError(
                f"MCP server {self.spec.name!r} did not connect.",
            )
        return self.resource

    async def _wait_connected_action(self) -> str:
        shutdown = asyncio.create_task(self._shutdown.wait())
        reconnect = asyncio.create_task(self._reconnect.wait())
        try:
            done, _ = await asyncio.wait(
                {shutdown, reconnect},
                timeout=self.spec.keepalive_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self._shutdown.is_set():
                return "shutdown"
            if reconnect in done:
                self._reconnect.clear()
                return "reconnect"
            resource = self.resource
            if resource is None:
                raise ConnectionError("Managed MCP resource disappeared.")
            async with self._rpc_lock:
                ping = getattr(resource, "send_ping", None)
                if callable(ping):
                    await asyncio.wait_for(
                        ping(),
                        timeout=min(30.0, self.spec.connect_timeout),
                    )
                elif callable(getattr(resource, "list_tools", None)):
                    await asyncio.wait_for(
                        resource.list_tools(),
                        timeout=min(30.0, self.spec.connect_timeout),
                    )
            return "healthy"
        finally:
            for task in (shutdown, reconnect):
                if not task.done():
                    task.cancel()
            await asyncio.gather(shutdown, reconnect, return_exceptions=True)

    async def _park(self) -> str:
        shutdown = asyncio.create_task(self._shutdown.wait())
        reconnect = asyncio.create_task(self._reconnect.wait())
        try:
            await asyncio.wait(
                {shutdown, reconnect},
                timeout=self.spec.parked_retry_interval,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if self._shutdown.is_set():
                return "shutdown"
            self._reconnect.clear()
            return "retry"
        finally:
            for task in (shutdown, reconnect):
                if not task.done():
                    task.cancel()
            await asyncio.gather(shutdown, reconnect, return_exceptions=True)

    async def _run(self) -> None:
        failures = 0
        backoff = 1.0
        try:
            while not self._shutdown.is_set():
                await self._set_state(ServerState.CONNECTING)
                try:
                    async with self.spec.resource_factory() as resource:
                        self.resource = resource
                        self.connected_at = time.time()
                        self.generation += 1
                        if self.spec.discover is not None:
                            self.discovered = await _maybe_await(
                                self.spec.discover(resource),
                            )
                        failures = 0
                        backoff = 1.0
                        await self._set_state(ServerState.CONNECTED)
                        self._ready.set()

                        while True:
                            action = await self._wait_connected_action()
                            if action == "healthy":
                                continue
                            break
                        self.resource = None
                        self.discovered = None
                        if action == "shutdown":
                            break
                        continue
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    self.resource = None
                    self.discovered = None
                    failures += 1
                    await self._set_state(ServerState.DEGRADED, error)
                    if failures > self.spec.max_retries:
                        await self._set_state(ServerState.PARKED, error)
                        self._ready.set()
                        if await self._park() == "shutdown":
                            break
                        failures = 0
                        backoff = 1.0
                        self._ready.clear()
                        continue
                    delay = min(backoff, self.spec.max_backoff)
                    await asyncio.sleep(delay * random.uniform(0.8, 1.2))
                    backoff = min(backoff * 2.0, self.spec.max_backoff)
        finally:
            self.resource = None
            self.discovered = None
            self._ready.set()
            await self._set_state(ServerState.STOPPED)

    async def reconnect(self) -> Any:
        if self._task is None or self._task.done():
            return await self.start()
        old_generation = self.generation
        self._ready.clear()
        self._reconnect.set()
        deadline = asyncio.get_running_loop().time() + self.spec.connect_timeout
        while asyncio.get_running_loop().time() < deadline:
            if self.resource is not None and self.generation > old_generation:
                return self.resource
            if self.state in {ServerState.PARKED, ServerState.STOPPED}:
                break
            await asyncio.sleep(0.05)
        raise TimeoutError(f"MCP server {self.spec.name!r} did not reconnect.")

    async def stop(self) -> None:
        task = self._task
        if task is None:
            await self._set_state(ServerState.STOPPED)
            return
        await self._set_state(ServerState.STOPPING)
        self._shutdown.set()
        self._reconnect.set()
        try:
            await asyncio.wait_for(
                asyncio.shield(task),
                timeout=min(30.0, self.spec.connect_timeout),
            )
        except asyncio.TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._task = None

    async def call(
        self,
        method: str,
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        resource = self.resource
        if resource is None:
            raise ConnectionError(f"MCP server {self.spec.name!r} is not connected.")
        operation = getattr(resource, method, None)
        if not callable(operation):
            raise AttributeError(
                f"MCP server {self.spec.name!r} has no method {method!r}.",
            )
        async with self._rpc_lock:
            return await asyncio.wait_for(
                _maybe_await(operation(*args, **kwargs)),
                timeout=timeout or self.spec.connect_timeout,
            )

    def status(self) -> dict[str, Any]:
        tools = self.discovered
        if hasattr(tools, "tools"):
            tools = tools.tools
        tool_count = len(tools) if isinstance(tools, (list, tuple, set)) else 0
        return {
            "name": self.spec.name,
            "state": self.state.value,
            "connected": self.resource is not None,
            "disabled": not self.spec.enabled,
            "generation": self.generation,
            "tools": tool_count,
            "connected_at": self.connected_at,
            "error": str(self.error) if self.error is not None else None,
            "metadata": dict(self.spec.metadata),
        }


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class MCPHostManagerPlugin:
    """Register, connect, probe, refresh, and stop multiple MCP servers."""

    def __init__(self, *, on_state: StateHandler | None = None) -> None:
        self.on_state = on_state
        self._servers: dict[str, _ServerRuntime] = {}
        self._manager_lock = asyncio.Lock()

    def register(
        self,
        name: str,
        resource_factory: ResourceFactory,
        **options: Any,
    ) -> None:
        """Register a server specification without connecting it."""
        if not name or not callable(resource_factory):
            raise ValueError("name and callable resource_factory are required.")
        existing = self._servers.get(name)
        if existing is not None and existing._task is not None:
            raise RuntimeError(f"Cannot replace running MCP server {name!r}.")
        spec = ServerSpec(name=name, resource_factory=resource_factory, **options)
        self._servers[name] = _ServerRuntime(spec, self.on_state)

    def unregister(self, name: str) -> None:
        runtime = self._servers.get(name)
        if runtime is not None and runtime._task is not None:
            raise RuntimeError(f"Stop MCP server {name!r} before unregistering it.")
        self._servers.pop(name, None)

    async def start(self, name: str) -> Any:
        return await self._get(name).start()

    async def start_all(self) -> dict[str, Any | BaseException]:
        """Connect enabled servers concurrently and isolate failures."""
        runtimes = list(self._servers.values())
        outcomes = await asyncio.gather(
            *(runtime.start() for runtime in runtimes),
            return_exceptions=True,
        )
        return {
            runtime.spec.name: outcome
            for runtime, outcome in zip(runtimes, outcomes)
        }

    async def reconnect(self, name: str) -> Any:
        return await self._get(name).reconnect()

    async def stop(self, name: str) -> None:
        await self._get(name).stop()

    async def stop_all(self) -> dict[str, BaseException]:
        """Stop every owner task in parallel and retain shutdown errors."""
        async with self._manager_lock:
            runtimes = list(self._servers.values())
            outcomes = await asyncio.gather(
                *(runtime.stop() for runtime in runtimes),
                return_exceptions=True,
            )
        return {
            runtime.spec.name: outcome
            for runtime, outcome in zip(runtimes, outcomes)
            if isinstance(outcome, BaseException)
        }

    async def call(
        self,
        server_name: str,
        method: str,
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        return await self._get(server_name).call(
            method,
            *args,
            timeout=timeout,
            **kwargs,
        )

    def resource(self, name: str) -> Any:
        """Return the current live session/resource."""
        resource = self._get(name).resource
        if resource is None:
            raise ConnectionError(f"MCP server {name!r} is not connected.")
        return resource

    def statuses(self) -> list[dict[str, Any]]:
        return [runtime.status() for runtime in self._servers.values()]

    def connected_names(self) -> set[str]:
        return {
            name
            for name, runtime in self._servers.items()
            if runtime.resource is not None
        }

    async def probe(
        self,
        resource_factory: ResourceFactory,
        *,
        discover: DiscoverHandler | None = None,
        timeout: float = 60.0,
    ) -> Any:
        """Temporarily connect and disconnect without registering a server."""
        async def run() -> Any:
            async with resource_factory() as resource:
                return (
                    await _maybe_await(discover(resource))
                    if discover is not None
                    else resource
                )

        return await asyncio.wait_for(run(), timeout=timeout)

    def _get(self, name: str) -> _ServerRuntime:
        try:
            return self._servers[name]
        except KeyError as error:
            raise KeyError(f"MCP server {name!r} is not registered.") from error


class MCPHostThreadBridge:
    """Run async host operations from synchronous application threads."""

    def __init__(self, *, name: str = "mcp-host-loop") -> None:
        self.name = name
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._ready.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name=self.name,
                daemon=True,
            )
            self._thread.start()
        if not self._ready.wait(timeout=10.0):
            raise TimeoutError("MCP host event loop did not start.")

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True),
                )
            loop.close()
            self._loop = None

    def submit(self, awaitable: Awaitable[Any]) -> concurrent.futures.Future[Any]:
        self.start()
        loop = self._loop
        if loop is None:
            raise RuntimeError("MCP host event loop is unavailable.")
        return asyncio.run_coroutine_threadsafe(awaitable, loop)

    def run(self, awaitable: Awaitable[Any], timeout: float | None = None) -> Any:
        return self.submit(awaitable).result(timeout=timeout)

    def stop(self, timeout: float = 10.0) -> None:
        with self._lock:
            loop = self._loop
            thread = self._thread
            self._thread = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=timeout)

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

