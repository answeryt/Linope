# -*- coding: utf-8 -*-
"""Classify an action onto async I/O, CPU, GPU, sandbox, or human.

The router only names the lane. Host injects the actual worker pools.
Do not import wait-reason or scheduler siblings.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PLUGIN_NAME = "kernel_async_resource"
PLUGIN_VERSION = "1.0"

ASYNC_IO = "async_io"
CPU = "cpu"
GPU = "gpu"
SANDBOX = "sandbox"
HUMAN = "human"

DEFAULT_KINDS: dict[str, str] = {
    "llm": ASYNC_IO,
    "llm.call": ASYNC_IO,
    "mcp": ASYNC_IO,
    "tool.call": ASYNC_IO,
    "http": ASYNC_IO,
    "db": ASYNC_IO,
    "embedding": CPU,
    "parser": CPU,
    "code": SANDBOX,
    "sandbox": SANDBOX,
    "inference": GPU,
    "gpu": GPU,
    "human": HUMAN,
    "human.wait": HUMAN,
}


def classify(
    action: Mapping[str, Any] | str,
    *,
    table: Mapping[str, str] | None = None,
) -> str:
    """Return the execution lane for an event, tool name, or resource tag."""
    kinds = dict(DEFAULT_KINDS)
    if table:
        kinds.update(table)
    if isinstance(action, str):
        key = action
    else:
        key = str(
            action.get("resource")
            or action.get("name")
            or action.get("type")
            or ""
        )
    if key in kinds:
        return kinds[key]
    lowered = key.lower()
    for token, lane in kinds.items():
        if token and token in lowered:
            return lane
    return ASYNC_IO


class ResourceRouter:
    """Callable router Host can inject into dispatch."""

    def __init__(self, table: Mapping[str, str] | None = None) -> None:
        self.table = dict(table or {})

    def classify(self, action: Mapping[str, Any] | str) -> str:
        return classify(action, table=self.table)
