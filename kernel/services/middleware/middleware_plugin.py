# -*- coding: utf-8 -*-
"""Around-the-loop hooks for consume and publish.

Instances expose consume_scope/publish_scope. Do not import sibling
middleware implementations; Host stacks them as a list.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Any, Optional


PLUGIN_NAME = "kernel_middleware"
PLUGIN_VERSION = "1.0"


class BaseMiddleware:
    """Duck-typed middleware around one agent task."""

    def __init__(self, task: Any | None = None, /, *, context: Any | None = None) -> None:
        self.task = task
        self.context = context

    async def on_receive(self) -> None:
        return None

    async def after_processed(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: Optional[TracebackType] = None,
    ) -> bool | None:
        return False

    async def __aenter__(self) -> "BaseMiddleware":
        await self.on_receive()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: Optional[TracebackType] = None,
    ) -> bool | None:
        return await self.after_processed(exc_type, exc_val, exc_tb)

    async def consume_scope(
        self,
        call_next: Callable[..., Awaitable[Any]],
        task: Any,
    ) -> Any:
        return await call_next(task)

    async def publish_scope(
        self,
        call_next: Callable[..., Awaitable[Any]],
        command: Any,
    ) -> Any:
        return await call_next(command)
