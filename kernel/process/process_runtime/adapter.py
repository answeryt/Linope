"""Capability Runtime Adapter contract."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from kernel.resource.handle_view import ResourceContext


class CapabilityAdapter(Protocol):
    """Business-specific runtime loaded inside one Capability Process."""

    is_async: bool
    sync_thread_safe: bool

    def initialize(self, resource_context: ResourceContext, room: Any = None) -> None:
        ...

    def handle(self, request: dict[str, Any]) -> Any:
        ...

    async def handle_async(self, request: dict[str, Any]) -> Any:
        """Optional async entry point for non-blocking capability handlers."""
        ...

    def shutdown(self) -> None:
        ...


AdapterFactory = Callable[[], CapabilityAdapter]
