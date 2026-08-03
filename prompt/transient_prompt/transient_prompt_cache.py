"""Independent cache plugin for transient prompt bytes.

"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


class TransientPromptCacheError(RuntimeError):
    """Transient prompt cache operation failed."""


@dataclass(slots=True)
class TransientPromptCachePlugin:
    """Manage per-turn prompt values and persistent message sidecars."""

    name: str = "turn_transient_prompt_cache"
    priority: int = 100
    cache_attribute: str = "_transient_prompt_cache"
    sidecar_field: str = "api_content"
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def enabled(self, context: Mapping[str, Any] | None = None) -> bool:
        """Allow a host to bypass transient caching for one operation."""

        return bool((context or {}).get("use_transient_prompt_cache", True))

    def _cache(self, host: Any, *, create: bool) -> MutableMapping[str, str] | None:
        cache = getattr(host, self.cache_attribute, None)
        if cache is None and create:
            cache = {}
            try:
                setattr(host, self.cache_attribute, cache)
            except (AttributeError, TypeError) as exc:
                raise TransientPromptCacheError(
                    f"Host does not support cache attribute {self.cache_attribute!r}"
                ) from exc
        if cache is None:
            return None
        if not isinstance(cache, MutableMapping):
            raise TransientPromptCacheError(
                f"{self.cache_attribute} must contain a mutable mapping or None"
            )
        return cache

    def get(
        self,
        host: Any,
        turn_id: str,
        context: Mapping[str, Any] | None = None,
    ) -> str | None:
        """Return a cached prompt for one turn."""

        if not self.enabled(context):
            return None
        if not isinstance(turn_id, str) or not turn_id:
            raise ValueError("turn_id must be a non-empty string")
        with self._lock:
            cache = self._cache(host, create=False)
            value = None if cache is None else cache.get(turn_id)
            if value is not None and not isinstance(value, str):
                raise TransientPromptCacheError("cached prompt must be a string")
            return value

    def store(
        self,
        host: Any,
        turn_id: str,
        prompt: str,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        """Store an assembled prompt for reuse within one turn."""

        if not isinstance(turn_id, str) or not turn_id:
            raise ValueError("turn_id must be a non-empty string")
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")
        if not self.enabled(context):
            return prompt
        with self._lock:
            cache = self._cache(host, create=True)
            assert cache is not None
            cache[turn_id] = prompt
        return prompt

    def invalidate(self, host: Any, turn_id: str | None = None) -> None:
        """Drop one turn entry, or clear all transient entries on the host."""

        with self._lock:
            cache = self._cache(host, create=False)
            if cache is None:
                return
            if turn_id is None:
                cache.clear()
                return
            cache.pop(turn_id, None)

    def consume_host_text(self, host: Any, attribute: str) -> str:
        """Read and clear a staged one-shot string such as gateway notes."""

        if not isinstance(attribute, str) or not attribute:
            raise ValueError("attribute must be a non-empty string")
        with self._lock:
            value = getattr(host, attribute, "") or ""
            try:
                setattr(host, attribute, "")
            except (AttributeError, TypeError) as exc:
                raise TransientPromptCacheError(
                    f"Host does not support one-shot attribute {attribute!r}"
                ) from exc
        return value if isinstance(value, str) else ""

    def stamp_sidecar(
        self,
        message: MutableMapping[str, Any],
        api_content: str | None,
    ) -> bool:
        """Store exact API text only when it differs from clean message text."""

        if not isinstance(message, MutableMapping):
            raise TypeError("message must be a mutable mapping")
        if api_content is None:
            message.pop(self.sidecar_field, None)
            return False
        if not isinstance(api_content, str):
            raise TypeError("api_content must be a string or None")
        if not api_content or api_content == message.get("content"):
            message.pop(self.sidecar_field, None)
            return False
        message[self.sidecar_field] = api_content
        return True

    def extract_sidecar(self, message: Mapping[str, Any]) -> str | None:
        """Return the exact API text carried by a message, when valid."""

        value = message.get(self.sidecar_field)
        return value if isinstance(value, str) and value else None

    def substitute_sidecar(self, api_message: MutableMapping[str, Any]) -> str | None:
        """Pop the bookkeeping field and replace provider-facing content."""

        value = api_message.pop(self.sidecar_field, None)
        if (
            isinstance(value, str)
            and value
            and api_message.get("role") in {"user", "assistant"}
        ):
            api_message["content"] = value
            return value
        return None

    def drop_sidecar(self, message: MutableMapping[str, Any]) -> None:
        """Invalidate exact API text after the clean message was rewritten."""

        message.pop(self.sidecar_field, None)


TRANSIENT_PROMPT_CACHE_PLUGIN = TransientPromptCachePlugin()


def consume_gateway_turn_notes(
    host: Any,
    *,
    attribute: str = "_gateway_turn_context_notes",
) -> str:
    """Consume the default gateway one-shot note attribute."""

    return TRANSIENT_PROMPT_CACHE_PLUGIN.consume_host_text(host, attribute)


def stamp_transient_api_content(
    message: MutableMapping[str, Any],
    api_content: str | None,
) -> bool:
    """Stamp exact provider bytes with the default cache plugin."""

    return TRANSIENT_PROMPT_CACHE_PLUGIN.stamp_sidecar(message, api_content)


__all__ = [
    "TRANSIENT_PROMPT_CACHE_PLUGIN",
    "TransientPromptCacheError",
    "TransientPromptCachePlugin",
    "consume_gateway_turn_notes",
    "stamp_transient_api_content",
]
