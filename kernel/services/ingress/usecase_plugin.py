# -*- coding: utf-8 -*-
"""Pass one ingress activation through middleware into the Process Runtime."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Awaitable


PLUGIN_NAME = "kernel_task_usecase"
PLUGIN_VERSION = "2.0"


class ProcessActivationInvalid(ValueError):
    """The ingress payload cannot create or resume a Process."""


async def _call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _wrap(
    middleware: Any,
    call_next: Callable[[Mapping[str, Any]], Awaitable[Any]],
) -> Callable[[Mapping[str, Any]], Awaitable[Any]]:
    consume = getattr(middleware, "consume_scope", None)
    if not callable(consume):
        return call_next

    async def wrapped(activation: Mapping[str, Any]) -> Any:
        return await consume(call_next, activation)

    return wrapped


class ProcessUsecase:
    """Resolve and activate one Process; Process handlers own goal progression."""

    def __init__(
        self,
        *,
        runtime: Any,
        middlewares: Sequence[Any] = (),
        logger: logging.Logger | None = None,
    ) -> None:
        if runtime is None or not callable(getattr(runtime, "activate", None)):
            raise TypeError("runtime with activate is required")
        self.runtime = runtime
        self.middlewares = list(middlewares)
        self.logger = logger or logging.getLogger(PLUGIN_NAME)
        self.in_flight = 0
        self.running = True

    async def process_task(self, activation: Mapping[str, Any]) -> Any:
        if not self.running:
            return None
        if not isinstance(activation, Mapping) or not activation.get("process_type"):
            raise ProcessActivationInvalid(
                "activation must be a mapping with process_type"
            )
        self.in_flight += 1
        try:
            call = self._activate
            for middleware in reversed(self.middlewares):
                call = _wrap(middleware, call)
            return await call(activation)
        finally:
            self.in_flight = max(0, self.in_flight - 1)

    async def _activate(self, activation: Mapping[str, Any]) -> Any:
        return await _call(self.runtime.activate, activation)

    async def stop(self) -> None:
        self.running = False


AgentTaskUsecase = ProcessUsecase
AgentTaskInvalid = ProcessActivationInvalid
