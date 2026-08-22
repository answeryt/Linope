# -*- coding: utf-8 -*-
"""Agent service lifecycle: startup hooks, start brokers, shutdown hooks.

Brokers are injected duck-typed objects with start/stop. This plugin does
not import broker or app siblings.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable, Sequence
from typing import Any


PLUGIN_NAME = "kernel_application"
PLUGIN_VERSION = "1.0"

Hook = Callable[..., Any]


async def _call(func: Hook, *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


class AgentApplication:
    """Open and close the agent worker process."""

    def __init__(
        self,
        *,
        brokers: Sequence[Any] = (),
        on_startup: Sequence[Hook] = (),
        after_startup: Sequence[Hook] = (),
        on_shutdown: Sequence[Hook] = (),
        after_shutdown: Sequence[Hook] = (),
        logger: logging.Logger | None = None,
    ) -> None:
        self.brokers = list(brokers)
        self._on_startup = list(on_startup)
        self._after_startup = list(after_startup)
        self._on_shutdown = list(on_shutdown)
        self._after_shutdown = list(after_shutdown)
        self.logger = logger or logging.getLogger(PLUGIN_NAME)
        self.running = False

    def add_broker(self, broker: Any) -> None:
        if broker in self.brokers:
            raise ValueError(f"broker already added: {broker}")
        self.brokers.append(broker)

    def on_startup(self, func: Hook) -> Hook:
        self._on_startup.append(func)
        return func

    def after_startup(self, func: Hook) -> Hook:
        self._after_startup.append(func)
        return func

    def on_shutdown(self, func: Hook) -> Hook:
        self._on_shutdown.append(func)
        return func

    def after_shutdown(self, func: Hook) -> Hook:
        self._after_shutdown.append(func)
        return func

    async def start(self, **options: Any) -> None:
        self.logger.info("agent service starting")
        for func in self._on_startup:
            await _call(func, **options)
        for broker in self.brokers:
            connect = getattr(broker, "connect", None)
            if callable(connect):
                await _call(connect)
            await _call(broker.start)
        for func in self._after_startup:
            await _call(func)
        self.running = True
        self.logger.info("agent service started")

    async def stop(self) -> None:
        self.logger.info("agent service shutting down")
        for func in self._on_shutdown:
            await _call(func)
        for broker in self.brokers:
            await _call(broker.stop)
        for func in self._after_shutdown:
            await _call(func)
        self.running = False
        self.logger.info("agent service shut down")
