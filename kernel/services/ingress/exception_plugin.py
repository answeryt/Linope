# -*- coding: utf-8 -*-
"""Keep agent errors from killing the worker.

Handlers are injected by exception type. Invalid tasks and cancellations
have defaults; Host can add_handler for model timeouts and the like.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping
from typing import Any


PLUGIN_NAME = "kernel_exception"
PLUGIN_VERSION = "1.0"

ExceptionHandler = Callable[..., Any]


class AgentCancelled(Exception):
    """The current agent task was cancelled."""


class AgentTimeout(Exception):
    """The agent loop exceeded cancel_after."""


class AgentTaskInvalid(ValueError):
    """Task payload cannot be processed."""


async def _call(func: ExceptionHandler, *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _handler_for(
    table: dict[type[BaseException], ExceptionHandler],
    exc: BaseException,
) -> ExceptionHandler | None:
    for cls in type(exc).__mro__:
        if cls in table:
            return table[cls]
        name = getattr(cls, "__name__", None)
        for key, handler in table.items():
            if getattr(key, "__name__", None) == name:
                return handler
    return None


class ExceptionMiddleware:
    """Map exception types to handlers around one task."""

    def __init__(
        self,
        handlers: dict[type[BaseException], ExceptionHandler] | None = None,
        publish_handlers: dict[type[BaseException], ExceptionHandler] | None = None,
    ) -> None:
        self._handlers: dict[type[BaseException], ExceptionHandler] = dict(handlers or {})
        self._publish_handlers: dict[type[BaseException], ExceptionHandler] = dict(
            publish_handlers or {}
        )

    def add_handler(
        self,
        exc: type[BaseException],
        func: ExceptionHandler,
        *,
        publish: bool = False,
    ) -> ExceptionHandler:
        bucket = self._publish_handlers if publish else self._handlers
        bucket[exc] = func
        return func

    async def consume_scope(
        self,
        call_next: Callable[..., Awaitable[Any]],
        task: Mapping[str, Any],
    ) -> Any:
        try:
            return await call_next(task)
        except Exception as exc:
            publish = _handler_for(self._publish_handlers, exc)
            if publish is not None:
                return await _call(publish, exc, task=task)
            handler = _handler_for(self._handlers, exc)
            if handler is not None:
                await _call(handler, exc, task=task)
                return None
            raise
