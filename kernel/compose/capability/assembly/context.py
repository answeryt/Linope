"""Resource container used for capability injection and runtime lifecycle."""

from __future__ import annotations

import asyncio
import heapq
import inspect
import weakref
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from kernel.compose.capability.assembly.cap_bus import CapBus

Cleanup = Callable[[], Any]
CapabilityListener = Callable[["ResourceContainer", "CapabilityBroadcast"], Any]
LifecycleListener = Callable[["ListenerLifecycleEvent"], Any]


class NoService(LookupError):
    """No resource has been provided under the requested name."""


@dataclass(frozen=True, slots=True)
class ResourceLease:
    """Lease of one requested capability and the owners needed by it."""

    lease_id: str
    capability: str
    owners: tuple[str, ...]
    owner: str
    created_at: float


@dataclass(frozen=True, slots=True)
class CapabilityBroadcast:
    """Broadcast payload for one capability request."""

    ticket_id: str
    capability: str
    constraints: Mapping[str, Any]
    owner: str
    priority: int
    created_at: float
    trace_id: str
    idempotency_key: str
    deadline_at: float | None
    attempt: int
    max_attempts: int
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ListenerResult:
    """Listener response used by capability broadcast worker."""

    handled: bool = False
    stop: bool = False
    owners: tuple[str, ...] = ()
    value: Any = None


@dataclass(frozen=True, slots=True)
class CapabilityDeadLetter:
    """Persisted request failure after retries are exhausted."""

    ticket_id: str
    capability: str
    owner: str
    trace_id: str
    attempt: int
    max_attempts: int
    reason: str
    error: str
    created_at: float
    failed_at: float


@dataclass(frozen=True, slots=True)
class ListenerLifecycleEvent:
    """Lifecycle event emitted when listeners are connected/disconnected."""

    event: str
    listener_id: str
    name: str
    priority: int
    capability: str | None
    prefix: str | None
    weak: bool
    reason: str
    created_at: float


@dataclass(slots=True)
class _QueuedRequest:
    ticket_id: str
    capability: str
    constraints: Mapping[str, Any]
    owner: str
    priority: int
    created_at: float
    trace_id: str
    idempotency_key: str
    deadline_at: float | None
    max_attempts: int
    retry_backoff_seconds: float
    future: asyncio.Future[ResourceLease]
    attempt: int = 0
    status: str = "queued"
    lease: ResourceLease | None = None
    error: Exception | None = None
    cancelled_reason: str | None = None


@dataclass(slots=True)
class _RegisteredListener:
    listener_id: str
    name: str
    priority: int
    capability: str | None
    prefix: str | None
    weak: bool
    callback: Any


@runtime_checkable
class ResourceContext(Protocol):
    """Resource container protocol used by capability plugins."""

    def provide(
        self,
        name: str,
        value: Any,
        *,
        contract: str | None = None,
        scope: str = "service",
        replace: bool = True,
        aliases: Iterable[str] = (),
    ) -> Cleanup: ...

    def get(self, name: str) -> Any: ...

    def get_all(self, capability: str) -> tuple[Any, ...]: ...

    def capabilities(self, name: str | None = None) -> tuple[Any, ...]: ...

    def has_service(self, name: str) -> bool: ...

    def track(self, cleanup: Cleanup) -> Cleanup: ...


# Backward-compatible alias used by existing modules.
CapabilityContext = ResourceContext


class _Runtime:
    def __init__(
        self,
        repo: Path,
        *,
        files: Any,
        capabilities: Any,
        descriptors: Mapping[str, Any] | None = None,
        ensure_capability: Callable[..., Any] | None = None,
    ) -> None:
        self.repo = repo.resolve()
        self.files = files
        self.effects: dict[Any, list[Cleanup]] = defaultdict(list)
        self.capabilities = capabilities
        self.ensure_capability = ensure_capability
        self.descriptors: dict[str, Any] = dict(descriptors or {})
        self.active_owners: set[str] = set()
        self.owner_refs: dict[str, int] = defaultdict(int)
        self.owner_idle_since: dict[str, float] = {}
        self.leases: dict[str, ResourceLease] = {}
        self.requests: dict[str, _QueuedRequest] = {}
        self.request_heap: list[tuple[float, int, int, str]] = []
        self.request_sequence = 0
        self.listeners: list[_RegisteredListener] = []
        self.connected_hooks: list[LifecycleListener] = []
        self.disconnected_hooks: list[LifecycleListener] = []
        self.dead_letters: list[CapabilityDeadLetter] = []
        self.injected: list[Any] = []
        self.worker_task: asyncio.Task[Any] | None = None
        self.broadcast_muted = 0
        self.closed = False

    def unload_owner(self, owner: Any) -> None:
        self.active_owners.discard(str(owner))
        cleanups = self.effects.pop(owner, [])
        for cleanup in reversed(cleanups):
            cleanup()


class ResourceContainer:
    """Runtime resource container for capability modules and services."""

    def __init__(
        self,
        *,
        repo: str | Path | None = None,
        files: Any = None,
        capabilities: Any = None,
        descriptors: Mapping[str, Any] | None = None,
        ensure_capability: Callable[..., Any] | None = None,
        _runtime: _Runtime | None = None,
        _owner: Any = None,
    ) -> None:
        if _runtime is not None:
            self._runtime = _runtime
            self._owner = _owner
            return
        if files is None or capabilities is None:
            raise TypeError("ResourceContainer needs files and capabilities")
        root = Path(repo) if repo is not None else Path.cwd()
        self._runtime = _Runtime(
            root,
            files=files,
            capabilities=capabilities,
            descriptors=descriptors,
            ensure_capability=ensure_capability,
        )
        self._owner = _owner

    @property
    def cap_bus(self) -> CapBus:
        return CapBus(self)

    def inject(self, capability: Any) -> Any:
        from kernel.compose.capability.capability import inject as inject_capability

        return inject_capability(capability, self)

    def bind(self, owner: str) -> "ResourceContainer":
        return ResourceContainer(_runtime=self._runtime, _owner=owner)

    def provide(
        self,
        name: str,
        value: Any,
        *,
        contract: str | None = None,
        scope: str = "service",
        replace: bool = True,
        aliases: Iterable[str] = (),
    ) -> Cleanup:
        provider = str(self._owner) if self._owner is not None else "<host>"
        dispose = self._runtime.capabilities.register(
            name,
            value,
            provider=provider,
            contract=contract,
            scope=scope,
            replace=replace,
            aliases=aliases,
        )
        if self._owner is not None:
            self._runtime.effects[self._owner].append(dispose)
        return dispose

    def remember(self, descriptor: Any) -> None:
        self._runtime.descriptors[descriptor.artifact.name] = descriptor

    def descriptor(self, name: str) -> Any:
        try:
            return self._runtime.descriptors[name]
        except KeyError as error:
            raise NoService(name) from error

    def descriptors(self) -> tuple[Any, ...]:
        return tuple(self._runtime.descriptors.values())

    def module(self, name: str) -> Any:
        descriptor = self.descriptor(name)
        source = descriptor.artifact.source
        if not source:
            raise NoService(f"{name} has no source path")
        return self._runtime.files.load("resource", name, source, required=None)

    def get(self, name: str) -> Any:
        try:
            return self._runtime.capabilities.get(name)
        except LookupError:
            try:
                return self.module(name)
            except LookupError as error:
                raise NoService(name) from error

    def get_all(self, capability: str) -> tuple[Any, ...]:
        return self._runtime.capabilities.get_all(capability)

    def capabilities(self, name: str | None = None) -> tuple[Any, ...]:
        return self._runtime.capabilities.capabilities(name)

    def has_service(self, name: str) -> bool:
        try:
            self._runtime.capabilities.get(name)
        except LookupError:
            return False
        return True

    def track(self, cleanup: Cleanup) -> Cleanup:
        if not callable(cleanup):
            raise TypeError("cleanup must be callable")
        if self._owner is not None:
            self._runtime.effects[self._owner].append(cleanup)
        return cleanup

    def mark_owner_loaded(self, owner: str) -> None:
        self._runtime.active_owners.add(owner)

    def is_owner_loaded(self, owner: str) -> bool:
        return owner in self._runtime.active_owners

    def listen_capability(
        self,
        callback: CapabilityListener,
        *,
        name: str | None = None,
        priority: int = 0,
        capability: str | None = None,
        prefix: str | None = None,
        weak: bool = True,
    ) -> Cleanup:
        """Register a capability listener used by async capability broadcasts."""
        if not callable(callback):
            raise TypeError("capability listener must be callable")
        if capability is not None and (not isinstance(capability, str) or not capability):
            raise ValueError("capability filter must be a non-empty string")
        if prefix is not None and (not isinstance(prefix, str) or not prefix):
            raise ValueError("prefix filter must be a non-empty string")
        listener_id = uuid4().hex
        callback_ref, weak_mode = self._callback_ref(
            callback,
            weak=weak,
            cleanup=lambda _ref: self._remove_listener(listener_id, reason="garbage_collected"),
        )
        registration = _RegisteredListener(
            listener_id=listener_id,
            name=name or getattr(callback, "__name__", "anonymous_listener"),
            priority=int(priority),
            capability=capability,
            prefix=prefix,
            weak=weak_mode,
            callback=callback_ref,
        )
        self._runtime.listeners.append(registration)
        self._runtime.listeners.sort(key=lambda item: item.priority, reverse=True)
        self._emit_listener_event("connected", registration, reason="explicit")

        def dispose() -> None:
            self._remove_listener(listener_id, reason="explicit")

        return self.track(dispose)

    def listen_listener_connected(self, callback: LifecycleListener) -> Cleanup:
        if not callable(callback):
            raise TypeError("listener_connected hook must be callable")
        self._runtime.connected_hooks.append(callback)

        def dispose() -> None:
            self._runtime.connected_hooks[:] = [
                item for item in self._runtime.connected_hooks if item is not callback
            ]

        return self.track(dispose)

    def listen_listener_disconnected(self, callback: LifecycleListener) -> Cleanup:
        if not callable(callback):
            raise TypeError("listener_disconnected hook must be callable")
        self._runtime.disconnected_hooks.append(callback)

        def dispose() -> None:
            self._runtime.disconnected_hooks[:] = [
                item for item in self._runtime.disconnected_hooks if item is not callback
            ]

        return self.track(dispose)

    @contextmanager
    def connected_listener(
        self,
        callback: CapabilityListener,
        *,
        name: str | None = None,
        priority: int = 0,
        capability: str | None = None,
        prefix: str | None = None,
        weak: bool = False,
    ):
        dispose = self.listen_capability(
            callback,
            name=name,
            priority=priority,
            capability=capability,
            prefix=prefix,
            weak=weak,
        )
        try:
            yield None
        finally:
            dispose()

    @contextmanager
    def muted_broadcast(self):
        self._runtime.broadcast_muted += 1
        try:
            yield None
        finally:
            self._runtime.broadcast_muted = max(0, self._runtime.broadcast_muted - 1)

    def listeners(self) -> tuple[tuple[str, int, str | None, str | None], ...]:
        self._prune_dead_listeners()
        return tuple(
            (item.name, item.priority, item.capability, item.prefix)
            for item in self._runtime.listeners
        )

    def has_listeners_for(self, capability: str) -> bool:
        self._prune_dead_listeners()
        return any(self._matches_listener(item, capability) for item in self._runtime.listeners)

    async def publish(
        self,
        capability: str,
        *,
        payload: Mapping[str, Any] | None = None,
        owner: str | None = None,
        priority: int = 0,
    ) -> Any:
        """Invoke matching subscribers with a payload. This is not a lease request."""
        if not isinstance(capability, str) or not capability:
            raise ValueError("capability must be a non-empty string")
        broadcast = CapabilityBroadcast(
            ticket_id=uuid4().hex,
            capability=capability,
            constraints={},
            owner=owner or str(self._owner or "<host>"),
            priority=int(priority),
            created_at=monotonic(),
            trace_id="",
            idempotency_key="",
            deadline_at=None,
            attempt=1,
            max_attempts=1,
            payload=dict(payload or {}),
        )
        outcome = await self._broadcast_capability(broadcast)
        if not outcome.handled:
            raise LookupError(f"no subscriber handled {capability!r}")
        return outcome.value

    async def submit_request(
        self,
        capability: str,
        *,
        constraints: Mapping[str, Any] | None = None,
        owner: str | None = None,
        priority: int = 0,
        trace_id: str | None = None,
        idempotency_key: str | None = None,
        timeout_seconds: float | None = None,
        max_attempts: int = 1,
        retry_backoff_seconds: float = 0.0,
    ) -> str:
        """Submit one capability request into the async priority queue."""
        if not isinstance(capability, str) or not capability:
            raise ValueError("capability must be a non-empty string")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds must be non-negative")
        loop = asyncio.get_running_loop()
        created_at = monotonic()
        deadline_at = (
            created_at + float(timeout_seconds)
            if timeout_seconds is not None
            else None
        )
        request = _QueuedRequest(
            ticket_id=uuid4().hex,
            capability=capability,
            constraints=dict(constraints or {}),
            owner=owner or "<anonymous>",
            priority=int(priority),
            created_at=created_at,
            trace_id=trace_id or uuid4().hex,
            idempotency_key=idempotency_key or uuid4().hex,
            deadline_at=deadline_at,
            max_attempts=int(max_attempts),
            retry_backoff_seconds=float(retry_backoff_seconds),
            future=loop.create_future(),
        )
        self._runtime.requests[request.ticket_id] = request
        # Use a shared immediate bucket so priority decides ordering.
        self._enqueue_request(request, ready_at=0.0)
        self._ensure_worker()
        return request.ticket_id

    async def wait_request(
        self,
        ticket_id: str,
        *,
        timeout: float | None = None,
    ) -> ResourceLease:
        """Wait asynchronously for a submitted request."""
        request = self._runtime.requests.get(ticket_id)
        if request is None:
            raise KeyError(f"unknown request ticket: {ticket_id}")
        self._ensure_worker()
        try:
            if timeout is None:
                lease = await request.future
            else:
                lease = await asyncio.wait_for(request.future, timeout=float(timeout))
        except asyncio.TimeoutError as error:
            self.cancel_request(ticket_id, reason="wait_timeout")
            raise TimeoutError(f"capability request timed out: {ticket_id}") from error
        except asyncio.CancelledError:
            self.cancel_request(ticket_id, reason="cancelled")
            raise
        finally:
            if request.status in {"done", "failed", "cancelled"}:
                self._runtime.requests.pop(ticket_id, None)
        return lease

    async def request_async(
        self,
        capability: str,
        *,
        constraints: Mapping[str, Any] | None = None,
        owner: str | None = None,
        priority: int = 0,
        timeout: float | None = None,
        trace_id: str | None = None,
        idempotency_key: str | None = None,
        max_attempts: int = 1,
        retry_backoff_seconds: float = 0.0,
    ) -> ResourceLease:
        """Submit and wait for one capability request."""
        ticket = await self.submit_request(
            capability,
            constraints=constraints,
            owner=owner,
            priority=priority,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            timeout_seconds=timeout,
            max_attempts=max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        return await self.wait_request(ticket, timeout=timeout)

    def cancel_request(self, ticket_id: str, *, reason: str = "cancelled") -> bool:
        """Cancel a queued or running request."""
        request = self._runtime.requests.get(ticket_id)
        if request is None:
            return False
        if request.status in {"done", "failed", "cancelled"}:
            return False
        request.status = "cancelled"
        request.cancelled_reason = reason
        if not request.future.done():
            request.future.cancel()
        return True

    def pending_requests(self) -> tuple[str, ...]:
        snapshot = []
        for ready_at, neg_priority, sequence, ticket_id in sorted(self._runtime.request_heap):
            request = self._runtime.requests.get(ticket_id)
            if request is None or request.status not in {"queued", "running"}:
                continue
            snapshot.append((ticket_id, -neg_priority, sequence, ready_at))
        return tuple(item[0] for item in snapshot)

    def dead_letters(self) -> tuple[CapabilityDeadLetter, ...]:
        return tuple(self._runtime.dead_letters)

    def clear_dead_letters(self) -> None:
        self._runtime.dead_letters.clear()

    def release_lease(
        self,
        lease: ResourceLease,
        *,
        eager: bool = True,
    ) -> tuple[str, ...]:
        """Release one lease and optionally unload idle owners immediately."""
        if lease.lease_id not in self._runtime.leases:
            return ()
        self._runtime.leases.pop(lease.lease_id, None)
        released: list[str] = []
        for owner in reversed(lease.owners):
            count = self._runtime.owner_refs.get(owner, 0)
            if count <= 1:
                self._runtime.owner_refs.pop(owner, None)
                self._runtime.owner_idle_since[owner] = monotonic()
                if eager:
                    self._runtime.unload_owner(owner)
                    released.append(owner)
                    self._runtime.owner_idle_since.pop(owner, None)
            else:
                self._runtime.owner_refs[owner] = count - 1
        return tuple(released)

    def collect_garbage(self, *, max_idle_seconds: float = 0.0) -> tuple[str, ...]:
        """Unload owners that are idle for at least max_idle_seconds."""
        threshold = float(max_idle_seconds)
        now = monotonic()
        candidates = [
            owner
            for owner, idle_since in self._runtime.owner_idle_since.items()
            if now - idle_since >= threshold
        ]
        released: list[str] = []
        for owner in candidates:
            if self._runtime.owner_refs.get(owner, 0) != 0:
                continue
            self._runtime.unload_owner(owner)
            self._runtime.owner_idle_since.pop(owner, None)
            released.append(owner)
        return tuple(released)

    def usage(self) -> dict[str, Any]:
        return {
            "active_owners": tuple(sorted(self._runtime.active_owners)),
            "leased_owners": dict(self._runtime.owner_refs),
            "active_leases": tuple(self._runtime.leases),
            "pending_requests": self.pending_requests(),
            "listeners": self.listeners(),
            "dead_letters": tuple(self._runtime.dead_letters),
        }

    def unload(self, owner: str | None = None) -> None:
        if self._runtime.closed:
            return
        if owner is None:
            try:
                for current_owner in list(self._runtime.effects.keys())[::-1]:
                    self._runtime.unload_owner(current_owner)
            finally:
                if self._runtime.worker_task is not None:
                    self._runtime.worker_task.cancel()
                    self._runtime.worker_task = None
                for request in self._runtime.requests.values():
                    if not request.future.done():
                        request.future.cancel()
                self._runtime.requests.clear()
                self._runtime.request_heap.clear()
                self._runtime.owner_refs.clear()
                self._runtime.owner_idle_since.clear()
                self._runtime.leases.clear()
                self._runtime.listeners.clear()
                self._runtime.connected_hooks.clear()
                self._runtime.disconnected_hooks.clear()
                self._runtime.dead_letters.clear()
                self._runtime.injected.clear()
                closer = getattr(self._runtime.files, "close", None)
                if callable(closer):
                    closer()
                self._runtime.closed = True
            return
        self._runtime.unload_owner(owner)
        self._runtime.owner_refs.pop(owner, None)
        self._runtime.owner_idle_since.pop(owner, None)

    def _ensure_worker(self) -> None:
        task = self._runtime.worker_task
        if task is not None and not task.done():
            return
        loop = asyncio.get_running_loop()
        self._runtime.worker_task = loop.create_task(self._run_worker())

    async def _run_worker(self) -> None:
        try:
            while self._runtime.request_heap:
                now = monotonic()
                ready_at, _neg_priority, _sequence, ticket_id = self._runtime.request_heap[0]
                wait_seconds = ready_at - now
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                    continue
                heapq.heappop(self._runtime.request_heap)
                request = self._runtime.requests.get(ticket_id)
                if request is None:
                    continue
                if request.status == "cancelled":
                    continue
                if request.deadline_at is not None and monotonic() > request.deadline_at:
                    self._fail_request(request, TimeoutError("request deadline reached"))
                    continue
                request.status = "running"
                request.attempt += 1
                try:
                    broadcast = CapabilityBroadcast(
                        ticket_id=request.ticket_id,
                        capability=request.capability,
                        constraints=request.constraints,
                        owner=request.owner,
                        priority=request.priority,
                        created_at=request.created_at,
                        trace_id=request.trace_id,
                        idempotency_key=request.idempotency_key,
                        deadline_at=request.deadline_at,
                        attempt=request.attempt,
                        max_attempts=request.max_attempts,
                    )
                    listener_result = await self._broadcast_capability(broadcast)
                    if request.status == "cancelled":
                        continue
                    if listener_result.handled and self._capability_available(request.capability):
                        owners = listener_result.owners or self._owner_chain_for_capability(
                            request.capability
                        )
                    else:
                        owners = self._ensure_capability(
                            request.capability,
                            constraints=request.constraints,
                        )
                    if request.status == "cancelled":
                        continue
                    lease = ResourceLease(
                        lease_id=uuid4().hex,
                        capability=request.capability,
                        owners=owners,
                        owner=request.owner,
                        created_at=monotonic(),
                    )
                    self._runtime.leases[lease.lease_id] = lease
                    for owner in owners:
                        self._runtime.owner_refs[owner] = self._runtime.owner_refs.get(owner, 0) + 1
                        self._runtime.owner_idle_since.pop(owner, None)
                    request.lease = lease
                    request.status = "done"
                    if not request.future.done():
                        request.future.set_result(lease)
                except Exception as error:
                    if self._should_retry(request):
                        request.status = "queued"
                        retry_at = monotonic() + self._retry_delay_seconds(request)
                        self._enqueue_request(request, ready_at=retry_at)
                    else:
                        self._fail_request(request, error)
        finally:
            self._runtime.worker_task = None

    async def _broadcast_capability(self, broadcast: CapabilityBroadcast) -> ListenerResult:
        if self._runtime.broadcast_muted > 0:
            return ListenerResult()
        self._prune_dead_listeners()
        handled = False
        owners: list[str] = []
        value: Any = None
        for listener in list(self._runtime.listeners):
            if not self._matches_listener(listener, broadcast.capability):
                continue
            callback = self._resolve_callback(listener)
            if callback is None:
                self._remove_listener(listener.listener_id, reason="garbage_collected")
                continue
            result = callback(self, broadcast)
            if inspect.isawaitable(result):
                result = await result
            outcome = self._listener_outcome(result)
            if outcome.handled:
                handled = True
                value = outcome.value
            for owner in outcome.owners:
                if owner not in owners:
                    owners.append(owner)
            if outcome.stop:
                break
        return ListenerResult(handled=handled, owners=tuple(owners), value=value)

    def _ensure_capability(
        self,
        capability: str,
        *,
        constraints: Mapping[str, Any],
    ) -> tuple[str, ...]:
        if self._runtime.ensure_capability is not None:
            owners = self._runtime.ensure_capability(self, capability, constraints)
            self.get(capability)
            return tuple(owners)
        if not self._capability_available(capability):
            self._activate_injected(capability, constraints=constraints)
        if not self._capability_available(capability):
            self.get(capability)
            return ()
        owners = self._owner_chain_for_capability(capability)
        self.get(capability)
        return owners

    def _activate_injected(
        self,
        capability: str,
        *,
        constraints: Mapping[str, Any],
    ) -> None:
        del constraints
        for item in list(self._runtime.injected):
            satisfies = getattr(item, "satisfies", None)
            if callable(satisfies) and not satisfies(capability):
                continue
            on_request = getattr(item, "on_request", None)
            if not callable(on_request):
                continue
            identity = getattr(item, "identity", capability)
            result = on_request(
                self.bind(str(identity)),
                CapabilityBroadcast(
                    ticket_id="",
                    capability=capability,
                    constraints={},
                    owner=str(self._owner or "<host>"),
                    priority=0,
                    created_at=monotonic(),
                    trace_id="",
                    idempotency_key="",
                    deadline_at=None,
                    attempt=1,
                    max_attempts=1,
                ),
            )
            if inspect.isawaitable(result):
                self._schedule_awaitable(result)
            if self._capability_available(capability):
                return

    def _capability_available(self, capability: str) -> bool:
        try:
            return bool(self.get_all(capability))
        except Exception:
            return False

    def _owner_chain_for_capability(self, capability: str) -> tuple[str, ...]:
        owners = []
        for item in self.capabilities(capability):
            provider = str(item.provider)
            if provider not in owners:
                owners.append(provider)
        return tuple(owners)

    def _matches_listener(self, listener: _RegisteredListener, capability: str) -> bool:
        if listener.capability is not None and listener.capability != capability:
            return False
        if listener.prefix is not None and not capability.startswith(listener.prefix):
            return False
        return True

    def _listener_outcome(self, result: Any) -> ListenerResult:
        if isinstance(result, ListenerResult):
            return result
        if isinstance(result, bool):
            return ListenerResult(handled=result)
        if isinstance(result, Mapping):
            raw_owners = result.get("owners", ())
            if isinstance(raw_owners, str):
                owners = (raw_owners,)
            else:
                owners = tuple(str(item) for item in raw_owners)
            return ListenerResult(
                handled=bool(result.get("handled", False)),
                stop=bool(result.get("stop", False)),
                owners=owners,
                value=result.get("value"),
            )
        return ListenerResult()

    def _callback_ref(
        self,
        callback: CapabilityListener,
        *,
        weak: bool,
        cleanup: Callable[[Any], None],
    ) -> tuple[Any, bool]:
        if not weak:
            return callback, False
        try:
            if inspect.ismethod(callback):
                return weakref.WeakMethod(callback, cleanup), True
            return weakref.ref(callback, cleanup), True
        except TypeError:
            return callback, False

    def _resolve_callback(self, listener: _RegisteredListener) -> Any | None:
        callback = listener.callback
        if listener.weak:
            resolved = callback()
            return resolved
        return callback

    def _remove_listener(self, listener_id: str, *, reason: str) -> None:
        for index, listener in enumerate(list(self._runtime.listeners)):
            if listener.listener_id != listener_id:
                continue
            self._runtime.listeners.pop(index)
            self._emit_listener_event("disconnected", listener, reason=reason)
            return

    def _emit_listener_event(
        self,
        event: str,
        listener: _RegisteredListener,
        *,
        reason: str,
    ) -> None:
        payload = ListenerLifecycleEvent(
            event=event,
            listener_id=listener.listener_id,
            name=listener.name,
            priority=listener.priority,
            capability=listener.capability,
            prefix=listener.prefix,
            weak=listener.weak,
            reason=reason,
            created_at=monotonic(),
        )
        hooks = (
            self._runtime.connected_hooks
            if event == "connected"
            else self._runtime.disconnected_hooks
        )
        for hook in list(hooks):
            outcome = hook(payload)
            if inspect.isawaitable(outcome):
                self._schedule_awaitable(outcome)

    def _schedule_awaitable(self, awaitable: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(awaitable)
            return
        loop.create_task(awaitable)

    def _prune_dead_listeners(self) -> None:
        for listener in list(self._runtime.listeners):
            if not listener.weak:
                continue
            if self._resolve_callback(listener) is None:
                self._remove_listener(listener.listener_id, reason="garbage_collected")

    def _enqueue_request(self, request: _QueuedRequest, *, ready_at: float) -> None:
        heapq.heappush(
            self._runtime.request_heap,
            (ready_at, -request.priority, self._runtime.request_sequence, request.ticket_id),
        )
        self._runtime.request_sequence += 1

    def _should_retry(self, request: _QueuedRequest) -> bool:
        if request.status == "cancelled":
            return False
        if request.attempt >= request.max_attempts:
            return False
        if request.deadline_at is not None and monotonic() >= request.deadline_at:
            return False
        return True

    def _retry_delay_seconds(self, request: _QueuedRequest) -> float:
        if request.retry_backoff_seconds <= 0:
            return 0.0
        factor = 2 ** max(request.attempt - 1, 0)
        return request.retry_backoff_seconds * factor

    def _fail_request(self, request: _QueuedRequest, error: Exception) -> None:
        request.error = error
        request.status = "failed"
        dead_letter = CapabilityDeadLetter(
            ticket_id=request.ticket_id,
            capability=request.capability,
            owner=request.owner,
            trace_id=request.trace_id,
            attempt=request.attempt,
            max_attempts=request.max_attempts,
            reason=request.cancelled_reason or type(error).__name__,
            error=str(error),
            created_at=request.created_at,
            failed_at=monotonic(),
        )
        self._runtime.dead_letters.append(dead_letter)
        if not request.future.done():
            request.future.set_exception(error)


# Backward-compatible alias used by existing modules.
Context = ResourceContainer
