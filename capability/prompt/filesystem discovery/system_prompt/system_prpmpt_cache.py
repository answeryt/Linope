"""Session-scoped system-prompt cache plugin.

The cache is stored on the host object, matching the ``_cached_system_prompt``
lifecycle used by the agent. This module does not import the agent or builder,
so it can be registered and tested independently.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


class SystemPromptCacheError(RuntimeError):
    """System-prompt cache operation failed."""


@dataclass(slots=True)
class SystemPromptCachePlugin:
    """Cache one fully assembled system prompt on a session host."""

    name: str = "session_system_prompt_cache"
    priority: int = 100
    cache_attribute: str = "_cached_system_prompt"
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def enabled(self, context: Mapping[str, Any] | None = None) -> bool:
        """Allow the host to bypass caching for an individual operation."""

        return bool((context or {}).get("use_system_prompt_cache", True))

    def get(self, host: Any) -> str | None:
        """Return the cached prompt, using ``None`` as the cache-miss sentinel."""

        cached = getattr(host, self.cache_attribute, None)
        if cached is None:
            return None
        if not isinstance(cached, str):
            raise SystemPromptCacheError(
                f"{self.cache_attribute} must contain a string or None"
            )
        return cached

    def store(self, host: Any, prompt: str) -> str:
        """Store an assembled prompt on the session host."""

        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")
        try:
            setattr(host, self.cache_attribute, prompt)
        except (AttributeError, TypeError) as exc:
            raise SystemPromptCacheError(
                f"Host does not support cache attribute {self.cache_attribute!r}"
            ) from exc
        return prompt

    def get_or_build(
        self,
        host: Any,
        builder: Callable[[], str],
        context: Mapping[str, Any] | None = None,
    ) -> str:
        """Return the cached prompt or build and cache it exactly once."""

        if not callable(builder):
            raise TypeError("builder must be callable")
        if not self.enabled(context):
            prompt = builder()
            if not isinstance(prompt, str):
                raise SystemPromptCacheError("System prompt builder must return a string")
            return prompt

        with self._lock:
            cached = self.get(host)
            if cached is not None:
                return cached
            prompt = builder()
            if not isinstance(prompt, str):
                raise SystemPromptCacheError("System prompt builder must return a string")
            return self.store(host, prompt)

    def invalidate(self, host: Any, *, reload_memory: bool = True) -> None:
        """Clear the prompt after compaction and optionally refresh memory."""

        with self._lock:
            try:
                setattr(host, self.cache_attribute, None)
            except (AttributeError, TypeError) as exc:
                raise SystemPromptCacheError(
                    f"Host does not support cache attribute {self.cache_attribute!r}"
                ) from exc

            if not reload_memory:
                return
            memory_store = getattr(host, "_memory_store", None)
            if memory_store is None:
                return
            load_from_disk = getattr(memory_store, "load_from_disk", None)
            if not callable(load_from_disk):
                raise SystemPromptCacheError(
                    "Host memory store does not provide load_from_disk()"
                )
            load_from_disk()


SYSTEM_PROMPT_CACHE_PLUGIN = SystemPromptCachePlugin()


def get_or_build_system_prompt(
    host: Any,
    builder: Callable[[], str],
    context: Mapping[str, Any] | None = None,
) -> str:
    """Build once per session and reuse the cached system prompt."""

    return SYSTEM_PROMPT_CACHE_PLUGIN.get_or_build(host, builder, context)


def invalidate_system_prompt_cache(
    host: Any,
    *,
    reload_memory: bool = True,
) -> None:
    """Invalidate the default cache after a context-compaction event."""

    SYSTEM_PROMPT_CACHE_PLUGIN.invalidate(host, reload_memory=reload_memory)


__all__ = [
    "SYSTEM_PROMPT_CACHE_PLUGIN",
    "SystemPromptCacheError",
    "SystemPromptCachePlugin",
    "get_or_build_system_prompt",
    "invalidate_system_prompt_cache",
]
