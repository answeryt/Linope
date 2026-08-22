# -*- coding: utf-8 -*-
"""In-process key/value memory on an Agent Process mapping.

This is not context compression. Host stores the returned copy on the
process table. Do not import PCB or table siblings.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any


PLUGIN_NAME = "kernel_process_memory"
PLUGIN_VERSION = "1.0"

MEMORY = "memory"


def get_memory(
    record: Mapping[str, Any],
    key: str,
    default: Any = None,
) -> Any:
    memory = record.get(MEMORY)
    if not isinstance(memory, Mapping):
        return default
    return memory.get(key, default)


def set_memory(record: Mapping[str, Any], key: str, value: Any) -> dict[str, Any]:
    """Return a copy with ``key`` written. Does not mutate ``record``."""
    memory: MutableMapping[str, Any] = dict(record.get(MEMORY) or {})
    memory[key] = value
    updated = dict(record)
    updated[MEMORY] = dict(memory)
    return updated


def update_memory(record: Mapping[str, Any], values: Mapping[str, Any]) -> dict[str, Any]:
    memory: MutableMapping[str, Any] = dict(record.get(MEMORY) or {})
    memory.update(values)
    updated = dict(record)
    updated[MEMORY] = dict(memory)
    return updated


def clear_memory(record: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    memory: MutableMapping[str, Any] = dict(record.get(MEMORY) or {})
    if keys:
        for key in keys:
            memory.pop(key, None)
    else:
        memory.clear()
    updated = dict(record)
    updated[MEMORY] = dict(memory)
    return updated
