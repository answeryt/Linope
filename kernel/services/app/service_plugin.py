# -*- coding: utf-8 -*-
"""Function-composed Service and final Agent = Service + Resources."""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from typing import Any


PLUGIN_NAME = "kernel_service"
PLUGIN_VERSION = "1.0"


async def _call(func: Any, *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def define_service(
    name: str,
    *,
    processes: Sequence[Mapping[str, Any]],
    ingress: Any | None = None,
    runtime: Any | None = None,
    worker: Any | None = None,
    queue: Any | None = None,
    store: Any | None = None,
    middleware: Sequence[Any] = (),
    **fields: Any,
) -> dict[str, Any]:
    if not name:
        raise ValueError("name is required")
    process_items = [dict(item) for item in processes]
    if not process_items:
        raise ValueError("at least one process definition is required")
    record = {
        "name": name,
        "processes": process_items,
        "ingress": ingress,
        "runtime": runtime,
        "worker": worker,
        "queue": queue,
        "store": store,
        "middleware": list(middleware),
    }
    record.update(fields)
    return record


class AgentSystem:
    """The assembled system. Agent is not a Process or personality object."""

    def __init__(self, service: Mapping[str, Any], resources: Any) -> None:
        self.service = dict(service)
        self.resources = resources
        self.running = False

    async def activate(self, activation: Mapping[str, Any]) -> dict[str, Any]:
        runtime = self._runtime()
        return await _call(runtime.activate, activation)

    async def run(self) -> None:
        """Hide transport pumping inside the Service deployment boundary."""
        ingress = self.service.get("ingress")
        if ingress is None:
            raise RuntimeError("service ingress is required for run")
        receive = getattr(ingress, "receive", None) or getattr(ingress, "get", None)
        if not callable(receive):
            raise TypeError("ingress must provide receive or get")
        self.running = True
        while self.running:
            activation = await _call(receive)
            if activation is None:
                continue
            await self.activate(activation)

    async def stop(self) -> None:
        self.running = False
        close = getattr(self.service.get("ingress"), "close", None)
        if callable(close):
            await _call(close)

    def _runtime(self) -> Any:
        runtime = self.service.get("runtime")
        if runtime is None or not callable(getattr(runtime, "activate", None)):
            raise TypeError("service runtime with activate is required")
        return runtime


def assemble_agent(
    *,
    service: Mapping[str, Any],
    resources: Any,
) -> AgentSystem:
    """Assemble the public Agent boundary from exactly Service + Resources."""
    if resources is None:
        raise TypeError("resources are required")
    runtime = service.get("runtime")
    if runtime is not None and getattr(runtime, "resources", None) is None:
        runtime.resources = resources
    return AgentSystem(service, resources)
