# -*- coding: utf-8 -*-
"""Registry of task subscribers, event publishers, and middlewares.

Host injects the resulting lists into the broker. This plugin does not
import broker or usecase siblings.
"""

from __future__ import annotations

from typing import Any
from weakref import WeakSet


PLUGIN_NAME = "kernel_registrator"
PLUGIN_VERSION = "1.0"


class Registrator:
    """Hold subscriber/publisher objects until the broker starts them."""

    def __init__(self) -> None:
        self._subscribers: WeakSet[Any] = WeakSet()
        self._publishers: WeakSet[Any] = WeakSet()
        self._persistent_subscribers: list[Any] = []
        self._persistent_publishers: list[Any] = []
        self.middlewares: list[Any] = []

    @property
    def subscribers(self) -> list[Any]:
        return list(self._persistent_subscribers)

    @property
    def publishers(self) -> list[Any]:
        return list(self._persistent_publishers)

    def add_subscriber(self, subscriber: Any, *, persistent: bool = True) -> Any:
        self._subscribers.add(subscriber)
        if persistent:
            self._persistent_subscribers.append(subscriber)
        return subscriber

    def add_publisher(self, publisher: Any, *, persistent: bool = True) -> Any:
        self._publishers.add(publisher)
        if persistent:
            self._persistent_publishers.append(publisher)
        return publisher

    def add_middleware(self, middleware: Any) -> None:
        """Innermost middleware: runs closest to the agent loop."""
        self.middlewares.append(middleware)

    def insert_middleware(self, middleware: Any) -> None:
        """Outermost middleware: runs first on consume."""
        self.middlewares.insert(0, middleware)
