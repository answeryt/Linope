# -*- coding: utf-8 -*-
"""Why an Agent Thread is not running.

Scheduler and resource router copy these strings; they must not import
this file. Agent Thread != OS Thread: waiting here does not occupy a
kernel thread.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PLUGIN_NAME = "kernel_thred_wait_reason"
PLUGIN_VERSION = "1.0"

WAITING_LLM = "waiting_llm"
WAITING_MCP = "waiting_mcp"
WAITING_HTTP = "waiting_http"
WAITING_DB = "waiting_db"
WAITING_AGENT = "waiting_agent"
WAITING_HUMAN = "waiting_human"
RUNNING_CPU = "running_cpu"
RUNNING_GPU = "running_gpu"
RUNNING_SANDBOX = "running_sandbox"

IO_REASONS = frozenset(
    {WAITING_LLM, WAITING_MCP, WAITING_HTTP, WAITING_DB, WAITING_AGENT}
)
WORKER_REASONS = frozenset({RUNNING_CPU, RUNNING_GPU, RUNNING_SANDBOX})
HUMAN_REASONS = frozenset({WAITING_HUMAN})


def wait_reason(record: Mapping[str, Any]) -> str | None:
    value = record.get("wait_reason")
    if value is None:
        return None
    text = str(value)
    return text or None


def is_io_wait(reason: str | None) -> bool:
    return reason in IO_REASONS


def is_worker(reason: str | None) -> bool:
    return reason in WORKER_REASONS


def is_human(reason: str | None) -> bool:
    return reason in HUMAN_REASONS
