# -*- coding: utf-8 -*-
"""Broker contract: connect, start subscribers, stop, ping.

Subscribers are injected (Redis stream, in-memory queue, …). This plugin
does not import stream or registrator siblings.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Sequence
from typing import Any


PLUGIN_NAME = "kernel_broker"
PLUGIN_VERSION = "1.0"


async def _call(func: Any, *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


class AgentBroker:
    """Start and stop a set of task subscribers and event publishers."""

    def __init__(
        self,
        *,
        subscribers: Sequence[Any] = (),
        publishers: Sequence[Any] = (),
        ping: Any | None = None,
        connect: Any | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.subscribers = list(subscribers)
        self.publishers = list(publishers)
        self._ping = ping
        self._connect = connect
        self._connection: Any = None
        self.running = False
        self.logger = logger or logging.getLogger(PLUGIN_NAME)

    def add_subscriber(self, subscriber: Any) -> Any:
        self.subscribers.append(subscriber)
        return subscriber

    def add_publisher(self, publisher: Any) -> Any:
        self.publishers.append(publisher)
        return publisher

    async def connect(self) -> Any:
        if self._connection is None and self._connect is not None:
            self._connection = await _call(self._connect)
        return self._connection

    async def start(self) -> None:
        for subscriber in self.subscribers:
            await _call(subscriber.start)
        for publisher in self.publishers:
            start = getattr(publisher, "start", None)
            if callable(start):
                await _call(start)
        self.running = True

    async def stop(self) -> None:
        for subscriber in self.subscribers:
            await _call(subscriber.stop)
        self.running = False

    async def ping(self, timeout: float | None = None) -> bool:
        if self._ping is None:
            return True
        result = self._ping(timeout) if timeout is not None else self._ping()
        if inspect.isawaitable(result):
            result = await result
        return bool(result)
