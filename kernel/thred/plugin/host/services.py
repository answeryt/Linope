"""Domain-neutral registries used to compose tools, models, and transforms."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterable, Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol


class RegistrationConflict(RuntimeError):
    """A route or node name is already owned by another registration."""


@dataclass(frozen=True, slots=True)
class Contribution:
    """Named domain object plus detached composition metadata."""

    name: str
    value: Any
    metadata: Mapping[str, Any]


class ContributionService:
    """Reversible registry for domains whose call contract stays plugin-owned."""

    def __init__(self, ctx: Any, domain: str) -> None:
        self.ctx = ctx
        self.domain = domain
        self._items: dict[str, Contribution] = {}

    def register(
        self,
        name: str,
        value: Any,
        **metadata: Any,
    ) -> Callable[[], None]:
        if not name:
            raise ValueError(f"{self.domain} contribution needs a name")
        if name in self._items:
            raise RegistrationConflict(
                f"{self.domain} contribution {name!r} already exists"
            )
        contribution = Contribution(name, value, dict(metadata))
        self._items[name] = contribution

        def dispose() -> None:
            if self._items.get(name) is contribution:
                self._items.pop(name, None)

        return self.ctx.track(dispose)

    def get(self, name: str) -> Any:
        try:
            return self._items[name].value
        except KeyError as error:
            raise LookupError(
                f"no {self.domain} contribution named {name!r}"
            ) from error

    def describe(self) -> tuple[Contribution, ...]:
        return tuple(self._items.values())


@dataclass(frozen=True, slots=True)
class ToolRegistration:
    name: str
    schema: Mapping[str, Any]
    handler: Callable[..., Any]


class ToolService:
    """Atomic registry for model-visible tool schemas and handlers."""

    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx
        self._tools: dict[str, ToolRegistration] = {}

    def register(
        self,
        schemas: Iterable[Mapping[str, Any]],
        handler: Callable[..., Any],
    ) -> Callable[[], None]:
        if not callable(handler):
            raise TypeError("tool handler must be callable")
        prepared: list[ToolRegistration] = []
        seen: set[str] = set()
        for schema in schemas:
            name = schema.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("tool schema needs a non-empty name")
            if name in seen or name in self._tools:
                raise RegistrationConflict(f"tool {name!r} is already registered")
            seen.add(name)
            prepared.append(ToolRegistration(name, dict(schema), handler))
        if not prepared:
            raise ValueError("tool registration must include at least one schema")
        for registration in prepared:
            self._tools[registration.name] = registration

        def dispose() -> None:
            for registration in prepared:
                if self._tools.get(registration.name) is registration:
                    self._tools.pop(registration.name, None)

        return self.ctx.track(dispose)

    def schemas(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item.schema) for item in self._tools.values())

    def dispatch(self, name: str, arguments: Mapping[str, Any], **injected: Any) -> Any:
        try:
            registration = self._tools[name]
        except KeyError as error:
            raise LookupError(f"no tool named {name!r}") from error
        return registration.handler(name, dict(arguments), **injected)


class ModelAdapter(Protocol):
    """Smallest provider contract; metadata methods remain adapter-owned."""

    def stream(self, request: Mapping[str, Any]) -> AsyncIterable[Any]:
        """Stream normalized chunks for one model request."""


ModelNext = Callable[[Mapping[str, Any]], AsyncIterable[Any]]
ModelMiddleware = Callable[
    [ModelNext, Mapping[str, Any], Mapping[str, Any] | None],
    AsyncIterable[Any],
]


@dataclass(frozen=True, slots=True)
class _ModelRoute:
    provider: str
    adapter: Any


class ModelService:
    """Provider registry with an around-call middleware waterfall."""

    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx
        self._routes: dict[str, _ModelRoute] = {}
        self._middleware: list[tuple[int, ModelMiddleware]] = []

    def register_adapter(
        self,
        providers: Iterable[str],
        adapter: ModelAdapter | Callable[..., Any],
    ) -> Callable[[], None]:
        names = tuple(providers)
        if not names or any(not isinstance(name, str) or not name for name in names):
            raise ValueError("model providers must contain non-empty names")
        if len(set(names)) != len(names) or any(name in self._routes for name in names):
            raise RegistrationConflict("model provider route is already registered")
        routes = tuple(_ModelRoute(name, adapter) for name in names)
        for route in routes:
            self._routes[route.provider] = route

        def dispose() -> None:
            for route in routes:
                if self._routes.get(route.provider) is route:
                    self._routes.pop(route.provider, None)

        return self.ctx.track(dispose)

    def register_middleware(
        self,
        middleware: ModelMiddleware,
        *,
        priority: int = 0,
    ) -> Callable[[], None]:
        if not callable(middleware):
            raise TypeError("model middleware must be callable")
        registration = (priority, middleware)
        self._middleware.append(registration)
        self._middleware.sort(key=lambda item: item[0], reverse=True)

        def dispose() -> None:
            if registration in self._middleware:
                self._middleware.remove(registration)

        return self.ctx.track(dispose)

    def providers(self) -> tuple[str, ...]:
        return tuple(self._routes)

    def stream(
        self,
        request: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> AsyncIterable[Any]:
        provider = request.get("provider")
        if not isinstance(provider, str) or provider not in self._routes:
            raise LookupError(f"no model adapter for provider {provider!r}")

        def terminal(value: Mapping[str, Any]) -> AsyncIterable[Any]:
            return _adapter_stream(self._routes[provider].adapter, value)

        call = terminal
        for _priority, middleware in reversed(self._middleware):
            next_call = call

            def wrapped(
                value: Mapping[str, Any],
                *,
                _middleware: ModelMiddleware = middleware,
                _next: ModelNext = next_call,
            ) -> AsyncIterable[Any]:
                return _middleware(_next, value, context)

            call = wrapped
        return call(dict(request))


@dataclass(frozen=True, slots=True)
class PipelineNode:
    name: str
    transform: Callable[[Any], Any]
    requires: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    before: tuple[str, ...] = ()
    after: tuple[str, ...] = ()
    priority: int = 0


class PipelineService:
    """Topologically compose named transforms without importing their modules."""

    def __init__(self, ctx: Any) -> None:
        self.ctx = ctx
        self._nodes: dict[str, PipelineNode] = {}

    def register(
        self,
        name: str,
        transform: Callable[[Any], Any],
        *,
        requires: Iterable[str] = (),
        provides: Iterable[str] = (),
        before: Iterable[str] = (),
        after: Iterable[str] = (),
        priority: int = 0,
    ) -> Callable[[], None]:
        if not name or not callable(transform):
            raise ValueError("pipeline node needs a name and callable transform")
        if name in self._nodes:
            raise RegistrationConflict(f"pipeline node {name!r} already exists")
        node = PipelineNode(
            name,
            transform,
            tuple(requires),
            tuple(provides),
            tuple(before),
            tuple(after),
            priority,
        )
        self._nodes[name] = node

        def dispose() -> None:
            if self._nodes.get(name) is node:
                self._nodes.pop(name, None)

        return self.ctx.track(dispose)

    def order(self, names: Iterable[str] | None = None) -> tuple[PipelineNode, ...]:
        selected_names = tuple(names) if names is not None else tuple(self._nodes)
        try:
            selected = {name: self._nodes[name] for name in selected_names}
        except KeyError as error:
            raise LookupError(f"unknown pipeline node {error.args[0]!r}") from error
        edges: dict[str, set[str]] = {name: set() for name in selected}
        providers: dict[str, list[str]] = {}
        for node in selected.values():
            for capability in node.provides:
                providers.setdefault(capability, []).append(node.name)
        for node in selected.values():
            for capability in node.requires:
                matches = providers.get(capability, [])
                if not matches:
                    raise LookupError(
                        f"pipeline node {node.name!r} requires missing "
                        f"capability {capability!r}"
                    )
                edges[node.name].update(matches)
            for dependency in node.after:
                if dependency in selected:
                    edges[node.name].add(dependency)
            for successor in node.before:
                if successor in selected:
                    edges[successor].add(node.name)
            edges[node.name].discard(node.name)
        ordered: list[PipelineNode] = []
        pending = dict(selected)
        while pending:
            ready = [
                node
                for name, node in pending.items()
                if not (edges[name] & pending.keys())
            ]
            if not ready:
                raise RuntimeError(f"pipeline cycle: {sorted(pending)!r}")
            ready.sort(key=lambda item: (-item.priority, selected_names.index(item.name)))
            for node in ready:
                ordered.append(node)
                pending.pop(node.name)
        return tuple(ordered)

    def run(self, value: Any, names: Iterable[str] | None = None) -> Any:
        current = value
        for node in self.order(names):
            current = node.transform(current)
            if inspect.isawaitable(current):
                close = getattr(current, "close", None)
                if callable(close):
                    close()
                raise TypeError(
                    f"pipeline node {node.name!r} is async; use run_async"
                )
        return current

    async def run_async(self, value: Any, names: Iterable[str] | None = None) -> Any:
        current = value
        for node in self.order(names):
            current = node.transform(current)
            if inspect.isawaitable(current):
                current = await current
        return current


def install_core_services(ctx: Any) -> None:
    """Publish domain registries as ordinary replaceable capabilities."""

    if not ctx.has_service("tools"):
        ctx.provide("tools", ToolService(ctx), contract="ToolService")
    if not ctx.has_service("llm"):
        ctx.provide("llm", ModelService(ctx), contract="ModelService")
    if not ctx.has_service("pipelines"):
        ctx.provide("pipelines", PipelineService(ctx), contract="PipelineService")
    for name in ("prompt", "compression", "sandbox", "mcp", "ui"):
        if not ctx.has_service(name):
            ctx.provide(
                name,
                ContributionService(ctx, name),
                contract="ContributionService",
            )


def _adapter_stream(
    adapter: ModelAdapter | Callable[..., Any],
    request: Mapping[str, Any],
) -> AsyncIterable[Any]:
    stream = getattr(adapter, "stream", None)
    result = stream(request) if callable(stream) else adapter(request)
    if isinstance(result, AsyncIterable):
        return result

    async def one() -> AsyncIterable[Any]:
        resolved = await result if isinstance(result, Awaitable) else result
        yield resolved

    return one()
