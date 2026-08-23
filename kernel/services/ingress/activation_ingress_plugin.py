# -*- coding: utf-8 -*-
"""Asynchronous in-memory ingress for Process activation mappings."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, TypeAlias


PLUGIN_NAME = "kernel_activation_ingress"
PLUGIN_VERSION = "1.0"

Activation: TypeAlias = dict[str, Any]


class InMemoryIngress:
    """Deliver copied activations without polling or exposing mutable state."""

    def __init__(self) -> None:
        self._items: deque[Activation] = deque()
        self._closed = False
        self._condition = asyncio.Condition()

    async def send(self, activation: Mapping[str, Any]) -> None:
        if not isinstance(activation, Mapping):
            raise TypeError("activation must be a mapping")
        copied = deepcopy(dict(activation))
        async with self._condition:
            if self._closed:
                raise RuntimeError("ingress is closed")
            self._items.append(copied)
            self._condition.notify(1)

    async def receive(self) -> Activation | None:
        async with self._condition:
            await self._condition.wait_for(lambda: bool(self._items) or self._closed)
            if self._items:
                return deepcopy(self._items.popleft())
            return None

    async def close(self) -> None:
        async with self._condition:
            self._closed = True
            self._condition.notify_all()

    @property
    def closed(self) -> bool:
        return self._closed
