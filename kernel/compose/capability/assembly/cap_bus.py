"""Capability bus wrapping the resource container listener table."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


class CapBus:
    """Publish/subscribe facade over the container's existing broadcast table."""

    def __init__(self, context: Any) -> None:
        self._context = context

    def subscribe(
        self,
        handler: Any,
        *,
        capability: str | None = None,
        prefix: str | None = None,
        name: str | None = None,
        priority: int = 0,
        weak: bool = False,
    ) -> Callable[[], Any]:
        callback = _as_listener(handler)
        label = name or getattr(handler, "name", None) or getattr(callback, "__name__", "subscriber")
        return self._context.listen_capability(
            callback,
            name=str(label),
            priority=priority,
            capability=capability,
            prefix=prefix,
            weak=weak,
        )

    async def publish(
        self,
        capability: str,
        payload: Mapping[str, Any] | None = None,
        *,
        owner: str | None = None,
        priority: int = 0,
    ) -> Any:
        return await self._context.publish(
            capability,
            payload=payload,
            owner=owner,
            priority=priority,
        )


def _as_listener(handler: Any) -> Callable[..., Any]:
    on_request = getattr(handler, "on_request", None)
    if callable(on_request) and not callable(handler):
        return on_request
    if callable(handler):
        return handler
    raise TypeError("cap bus subscriber must be callable or provide on_request")
