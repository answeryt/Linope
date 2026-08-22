# -*- coding: utf-8 -*-
"""Logical execution context for one Agent Thread.

Agent Thread != OS Thread. Other plugins accept Mapping and do not import
this file.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_thred_context"
PLUGIN_VERSION = "1.0"

THREAD_ID = "thread_id"
PROCESS_ID = "process_id"
NAME = "name"
STATE = "state"
WAIT_REASON = "wait_reason"
PARENT_ID = "parent_id"
CHILDREN = "children"
EXECUTION_ID = "execution_id"


def new_thread_id() -> str:
    return uuid4().hex


def build_thread(
    name: str,
    *,
    process_id: str | None = None,
    thread_id: str | None = None,
    state: str = "ready",
    wait_reason: str | None = None,
    parent_id: str | None = None,
    children: list[str] | tuple[str, ...] | None = None,
    execution_id: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    if not name:
        raise ValueError("name is required")
    record: MutableMapping[str, Any] = {
        THREAD_ID: thread_id or new_thread_id(),
        PROCESS_ID: process_id,
        NAME: name,
        STATE: state,
        WAIT_REASON: wait_reason,
        PARENT_ID: parent_id,
        CHILDREN: list(children or ()),
        EXECUTION_ID: execution_id,
    }
    record.update(fields)
    return dict(record)


def attach_child(record: Mapping[str, Any], child_id: str) -> dict[str, Any]:
    children = list(record.get(CHILDREN) or ())
    if child_id not in children:
        children.append(child_id)
    updated = dict(record)
    updated[CHILDREN] = children
    return updated
