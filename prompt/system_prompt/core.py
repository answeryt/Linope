"""Generic, cacheable, and mutually isolated system prompt plugin framework.

The core module is responsible for orchestration only and contains no
product-specific prompts. Plugins may only read ``PromptContext`` and return
text; they must not query, import, or invoke other plugins through the framework.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable


class PromptTier(str, Enum):
    """Fixed assembly tiers for system prompts."""

    STABLE = "stable"
    CONTEXT = "context"
    VOLATILE = "volatile"


_TIER_ORDER = {
    PromptTier.STABLE: 0,
    PromptTier.CONTEXT: 1,
    PromptTier.VOLATILE: 2,
}


class PromptPluginError(RuntimeError):
    """System prompt plugin error."""


class DuplicatePluginError(PromptPluginError):
    """A plugin with the same name was already registered."""


class PluginIsolationError(PromptPluginError):
    """A plugin declared a cross-plugin dependency forbidden by the framework."""


@dataclass(frozen=True, slots=True)
class PromptContext:
    """Read-only input shared by all plugins.

    ``values`` is shallow-copied and wrapped as a read-only mapping so plugins
    cannot pass state by mutating a shared dict. ``cache_key`` is supplied by
    the host per session; when ``None``, caching is disabled.
    """

    values: Mapping[str, Any] = field(default_factory=dict)
    cache_key: Hashable | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "values",
            MappingProxyType(dict(self.values)),
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def require(self, key: str) -> Any:
        try:
            return self.values[key]
        except KeyError as exc:
            raise PromptPluginError(f"Missing required prompt context: {key}") from exc


PromptOutput = str | Sequence[str] | None


@runtime_checkable
class SystemPromptPlugin(Protocol):
    """Protocol for an isolated prompt plugin.

    Plugins should depend only on this protocol and their own business logic.
    The framework does not expose the registry, builder, or other plugin
    instances to plugins, so plugins cannot invoke one another through it.
    """

    name: str
    tier: PromptTier
    priority: int

    def enabled(self, context: PromptContext) -> bool:
        """Return whether the plugin is enabled for the current context."""

    def render(self, context: PromptContext) -> PromptOutput:
        """Render one or more prompt fragments."""


@dataclass(frozen=True, slots=True)
class FunctionPromptPlugin:
    """Adapt a standalone function as a prompt plugin."""

    name: str
    render_fn: Callable[[PromptContext], PromptOutput]
    tier: PromptTier = PromptTier.STABLE
    priority: int = 100
    enabled_fn: Callable[[PromptContext], bool] | None = None

    def enabled(self, context: PromptContext) -> bool:
        return self.enabled_fn(context) if self.enabled_fn is not None else True

    def render(self, context: PromptContext) -> PromptOutput:
        return self.render_fn(context)


@dataclass(frozen=True, slots=True)
class PromptFragment:
    """A single normalized prompt fragment."""

    plugin: str
    tier: PromptTier
    priority: int
    content: str


@dataclass(frozen=True, slots=True)
class PromptParts:
    """Three prompt layers ordered for cache-friendly assembly."""

    stable: str = ""
    context: str = ""
    volatile: str = ""

    def join(self, separator: str = "\n\n") -> str:
        return separator.join(
            part
            for part in (self.stable, self.context, self.volatile)
            if part
        )

    def as_dict(self) -> dict[str, str]:
        return {
            PromptTier.STABLE.value: self.stable,
            PromptTier.CONTEXT.value: self.context,
            PromptTier.VOLATILE.value: self.volatile,
        }


@dataclass(frozen=True, slots=True)
class PluginFailure:
    """Plugin failure recorded in fault-tolerant mode."""

    plugin: str
    error: Exception


@dataclass(frozen=True, slots=True)
class PromptBuildResult:
    """System prompt build result with optional diagnostics."""

    parts: PromptParts
    fragments: tuple[PromptFragment, ...]
    failures: tuple[PluginFailure, ...] = ()

    @property
    def prompt(self) -> str:
        return self.parts.join()


@dataclass(frozen=True, slots=True)
class _RegisteredPlugin:
    plugin: SystemPromptPlugin
    order: int


class SystemPromptRegistry:
    """Maintains an isolated plugin set with no cross-plugin lookup."""

    def __init__(self) -> None:
        self._plugins: dict[str, _RegisteredPlugin] = {}
        self._next_order = 0
        self._revision = 0

    @property
    def revision(self) -> int:
        return self._revision

    def register(self, plugin: SystemPromptPlugin) -> None:
        self._validate(plugin)
        if plugin.name in self._plugins:
            raise DuplicatePluginError(f"System prompt plugin already exists: {plugin.name}")
        self._plugins[plugin.name] = _RegisteredPlugin(
            plugin=plugin,
            order=self._next_order,
        )
        self._next_order += 1
        self._revision += 1

    def unregister(self, name: str) -> bool:
        removed = self._plugins.pop(name, None)
        if removed is not None:
            self._revision += 1
            return True
        return False

    def clear(self) -> None:
        if self._plugins:
            self._plugins.clear()
            self._revision += 1

    def snapshot(self) -> tuple[SystemPromptPlugin, ...]:
        """Return a stably sorted plugin snapshot, not exposed to plugins."""

        entries = sorted(
            self._plugins.values(),
            key=lambda entry: (
                _TIER_ORDER[entry.plugin.tier],
                entry.plugin.priority,
                entry.order,
            ),
        )
        return tuple(entry.plugin for entry in entries)

    @staticmethod
    def _validate(plugin: SystemPromptPlugin) -> None:
        if not isinstance(plugin, SystemPromptPlugin):
            raise TypeError("Plugin must implement the SystemPromptPlugin protocol")
        if not isinstance(plugin.name, str) or not plugin.name.strip():
            raise ValueError("Plugin name must be a non-empty string")
        if not isinstance(plugin.tier, PromptTier):
            raise ValueError("Plugin tier must be a PromptTier")
        if not isinstance(plugin.priority, int):
            raise ValueError("Plugin priority must be an integer")

        # Explicitly reject common plugin dependency declarations. Composition
        # may only be done by the host via registration order and shared
        # context, not via a plugin dependency graph.
        for attribute in ("depends_on", "dependencies", "requires_plugins"):
            dependency = getattr(plugin, attribute, None)
            if dependency:
                raise PluginIsolationError(
                    f"Plugin {plugin.name!r} declared a forbidden cross-plugin dependency: {attribute}"
                )


class SystemPromptBuilder:
    """Invoke isolated plugins and assemble the system prompt."""

    def __init__(
        self,
        registry: SystemPromptRegistry | None = None,
        *,
        separator: str = "\n\n",
        fail_fast: bool = True,
        max_cache_entries: int = 128,
    ) -> None:
        if not separator:
            raise ValueError("separator must not be empty")
        if max_cache_entries < 0:
            raise ValueError("max_cache_entries must not be negative")
        self.registry = registry or SystemPromptRegistry()
        self.separator = separator
        self.fail_fast = fail_fast
        self.max_cache_entries = max_cache_entries
        self._cache: OrderedDict[
            tuple[int, Hashable], PromptBuildResult
        ] = OrderedDict()

    def build(
        self,
        context: PromptContext | Mapping[str, Any] | None = None,
        *,
        cache_key: Hashable | None = None,
        use_cache: bool = True,
    ) -> str:
        return self.build_result(
            context,
            cache_key=cache_key,
            use_cache=use_cache,
        ).parts.join(self.separator)

    def build_parts(
        self,
        context: PromptContext | Mapping[str, Any] | None = None,
        *,
        cache_key: Hashable | None = None,
        use_cache: bool = True,
    ) -> PromptParts:
        return self.build_result(
            context,
            cache_key=cache_key,
            use_cache=use_cache,
        ).parts

    def build_result(
        self,
        context: PromptContext | Mapping[str, Any] | None = None,
        *,
        cache_key: Hashable | None = None,
        use_cache: bool = True,
    ) -> PromptBuildResult:
        prompt_context = self._coerce_context(context, cache_key)
        effective_key = prompt_context.cache_key
        internal_key = (
            (self.registry.revision, effective_key)
            if use_cache and effective_key is not None and self.max_cache_entries
            else None
        )

        if internal_key is not None:
            cached = self._cache.get(internal_key)
            if cached is not None:
                self._cache.move_to_end(internal_key)
                return cached

        fragments: list[PromptFragment] = []
        failures: list[PluginFailure] = []
        for plugin in self.registry.snapshot():
            try:
                if not plugin.enabled(prompt_context):
                    continue
                for content in self._normalize_output(plugin.render(prompt_context)):
                    fragments.append(
                        PromptFragment(
                            plugin=plugin.name,
                            tier=plugin.tier,
                            priority=plugin.priority,
                            content=content,
                        )
                    )
            except Exception as exc:
                if self.fail_fast:
                    raise PromptPluginError(
                        f"System prompt plugin {plugin.name!r} failed"
                    ) from exc
                failures.append(PluginFailure(plugin=plugin.name, error=exc))

        parts = self._build_parts(fragments)
        result = PromptBuildResult(
            parts=parts,
            fragments=tuple(fragments),
            failures=tuple(failures),
        )
        if internal_key is not None:
            self._cache[internal_key] = result
            self._cache.move_to_end(internal_key)
            while len(self._cache) > self.max_cache_entries:
                self._cache.popitem(last=False)
        return result

    def invalidate(self, cache_key: Hashable | None = None) -> None:
        """Clear all cache entries, or clear cache for a specific host session."""

        if cache_key is None:
            self._cache.clear()
            return
        for key in tuple(self._cache):
            if key[1] == cache_key:
                self._cache.pop(key, None)

    @staticmethod
    def _coerce_context(
        context: PromptContext | Mapping[str, Any] | None,
        cache_key: Hashable | None,
    ) -> PromptContext:
        if isinstance(context, PromptContext):
            if cache_key is not None and cache_key != context.cache_key:
                raise ValueError("cache_key conflicts with PromptContext.cache_key")
            return context
        return PromptContext(values=context or {}, cache_key=cache_key)

    @staticmethod
    def _normalize_output(output: PromptOutput) -> tuple[str, ...]:
        if output is None:
            return ()
        candidates: Sequence[str] = (output,) if isinstance(output, str) else output
        normalized: list[str] = []
        for candidate in candidates:
            if not isinstance(candidate, str):
                raise TypeError("Plugin output must be a string, sequence of strings, or None")
            content = candidate.strip()
            if content:
                normalized.append(content)
        return tuple(normalized)

    def _build_parts(self, fragments: list[PromptFragment]) -> PromptParts:
        by_tier: dict[PromptTier, list[str]] = {
            PromptTier.STABLE: [],
            PromptTier.CONTEXT: [],
            PromptTier.VOLATILE: [],
        }
        for fragment in fragments:
            by_tier[fragment.tier].append(fragment.content)
        return PromptParts(
            stable=self.separator.join(by_tier[PromptTier.STABLE]),
            context=self.separator.join(by_tier[PromptTier.CONTEXT]),
            volatile=self.separator.join(by_tier[PromptTier.VOLATILE]),
        )


__all__ = [
    "DuplicatePluginError",
    "FunctionPromptPlugin",
    "PluginFailure",
    "PluginIsolationError",
    "PromptBuildResult",
    "PromptContext",
    "PromptFragment",
    "PromptOutput",
    "PromptParts",
    "PromptPluginError",
    "PromptTier",
    "SystemPromptBuilder",
    "SystemPromptPlugin",
    "SystemPromptRegistry",
]
