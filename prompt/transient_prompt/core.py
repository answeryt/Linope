"""Generic orchestration framework for one-shot prompt plugins.

Transient plugins are not cached. Each call to ``consume`` indicates the host
is building a new model request; plugins should synchronously clear their
source after returning prompt text so content is loaded at most once.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable


class TransientPromptPluginError(RuntimeError):
    """One-shot prompt plugin execution failed."""


class DuplicateTransientPluginError(TransientPromptPluginError):
    """A transient prompt plugin with the same name was already registered."""


@dataclass(frozen=True, slots=True)
class TransientPromptContext:
    """Read-only context passed to transient prompt plugins."""

    values: Mapping[str, Any] = field(default_factory=dict)

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
            raise TransientPromptPluginError(
                f"Missing required transient prompt context: {key}"
            ) from exc


TransientPromptOutput = str | Sequence[str] | None


@runtime_checkable
class TransientPromptPlugin(Protocol):
    """Protocol for an isolated one-shot prompt plugin."""

    name: str
    priority: int

    def enabled(self, context: TransientPromptContext) -> bool:
        """Return whether the plugin is enabled for this request."""

    def consume(self, context: TransientPromptContext) -> TransientPromptOutput:
        """Return and consume prompt text for this request."""


@dataclass(frozen=True, slots=True)
class TransientPromptFragment:
    """Prompt fragment produced after a single plugin consumption."""

    plugin: str
    priority: int
    content: str


class TransientPromptRegistry:
    """Maintains mutually isolated transient prompt plugins."""

    def __init__(self) -> None:
        self._plugins: dict[str, tuple[int, TransientPromptPlugin]] = {}
        self._next_order = 0

    def register(self, plugin: TransientPromptPlugin) -> None:
        if not isinstance(plugin, TransientPromptPlugin):
            raise TypeError("Plugin must implement the TransientPromptPlugin protocol")
        if not isinstance(plugin.name, str) or not plugin.name.strip():
            raise ValueError("Plugin name must be a non-empty string")
        if not isinstance(plugin.priority, int):
            raise ValueError("Plugin priority must be an integer")
        if plugin.name in self._plugins:
            raise DuplicateTransientPluginError(
                f"Transient prompt plugin already exists: {plugin.name}"
            )
        self._plugins[plugin.name] = (self._next_order, plugin)
        self._next_order += 1

    def unregister(self, name: str) -> bool:
        return self._plugins.pop(name, None) is not None

    def snapshot(self) -> tuple[TransientPromptPlugin, ...]:
        entries = sorted(
            self._plugins.values(),
            key=lambda entry: (entry[1].priority, entry[0]),
        )
        return tuple(plugin for _, plugin in entries)


class TransientPromptBuilder:
    """Consume plugins by priority and assemble the transient prompt for the current request."""

    def __init__(
        self,
        registry: TransientPromptRegistry | None = None,
        *,
        separator: str = "\n\n",
    ) -> None:
        if not separator:
            raise ValueError("separator must not be empty")
        self.registry = registry or TransientPromptRegistry()
        self.separator = separator

    def consume(
        self,
        context: TransientPromptContext | Mapping[str, Any] | None = None,
    ) -> str:
        return self.separator.join(
            fragment.content for fragment in self.consume_fragments(context)
        )

    def consume_fragments(
        self,
        context: TransientPromptContext | Mapping[str, Any] | None = None,
    ) -> tuple[TransientPromptFragment, ...]:
        prompt_context = (
            context
            if isinstance(context, TransientPromptContext)
            else TransientPromptContext(context or {})
        )
        fragments: list[TransientPromptFragment] = []
        for plugin in self.registry.snapshot():
            try:
                if not plugin.enabled(prompt_context):
                    continue
                for content in self._normalize(plugin.consume(prompt_context)):
                    fragments.append(
                        TransientPromptFragment(
                            plugin=plugin.name,
                            priority=plugin.priority,
                            content=content,
                        )
                    )
            except Exception as exc:
                raise TransientPromptPluginError(
                    f"Transient prompt plugin {plugin.name!r} failed"
                ) from exc
        return tuple(fragments)

    @staticmethod
    def _normalize(output: TransientPromptOutput) -> tuple[str, ...]:
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


__all__ = [
    "DuplicateTransientPluginError",
    "TransientPromptBuilder",
    "TransientPromptContext",
    "TransientPromptFragment",
    "TransientPromptOutput",
    "TransientPromptPlugin",
    "TransientPromptPluginError",
    "TransientPromptRegistry",
]
