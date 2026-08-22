# -*- coding: utf-8 -*-
"""Process Control Block mapping for one Agent Process.

Address space: state, memory, context, budget, child ids. Other plugins
accept Mapping and do not import this file.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_process_pcb"
PLUGIN_VERSION = "1.0"

PROCESS_ID = "process_id"
AGENT = "agent"
STATE = "state"
MEMORY = "memory"
CONTEXT = "context"
PARENT_ID = "parent_id"
CHILDREN = "children"
THREADS = "threads"
BUDGET = "budget"
GOAL = "goal"


def new_process_id() -> str:
    return uuid4().hex


def build_pcb(
    agent: str,
    *,
    process_id: str | None = None,
    state: str = "new",
    memory: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
    parent_id: str | None = None,
    children: list[str] | tuple[str, ...] | None = None,
    threads: list[str] | tuple[str, ...] | None = None,
    budget: Mapping[str, Any] | None = None,
    goal: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Build a PCB mapping. Extra fields are copied onto the record."""
    if not agent:
        raise ValueError("agent is required")
    pcb: MutableMapping[str, Any] = {
        PROCESS_ID: process_id or new_process_id(),
        AGENT: agent,
        STATE: state,
        MEMORY: dict(memory or {}),
        CONTEXT: dict(context or {}),
        PARENT_ID: parent_id,
        CHILDREN: list(children or ()),
        THREADS: list(threads or ()),
        BUDGET: dict(budget or {}),
    }
    if goal is not None:
        pcb[GOAL] = goal
    pcb.update(fields)
    return dict(pcb)


def attach_child(record: Mapping[str, Any], child_id: str) -> dict[str, Any]:
    children = list(record.get(CHILDREN) or ())
    if child_id not in children:
        children.append(child_id)
    updated = dict(record)
    updated[CHILDREN] = children
    return updated


def attach_thread(record: Mapping[str, Any], thread_id: str) -> dict[str, Any]:
    threads = list(record.get(THREADS) or ())
    if thread_id not in threads:
        threads.append(thread_id)
    updated = dict(record)
    updated[THREADS] = threads
    return updated
