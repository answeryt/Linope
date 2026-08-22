# -*- coding: utf-8 -*-
"""Decide who should run, suspend, or wait on a human.

Wait-reason strings are duplicated here so this file never imports the
thred wait-reason plugin. Scheduler does not start OS threads.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


PLUGIN_NAME = "kernel_async_scheduler"
PLUGIN_VERSION = "1.0"

RUN = "run"
SUSPEND = "suspend"
WAIT = "wait"

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
WAKE_TYPES = frozenset(
    {
        "user.message",
        "llm.response",
        "tool.result",
        "human.resume",
        "task.spawn",
        "llm.call",
        "tool.call",
        "task.done",
    }
)


def decide(record: Mapping[str, Any]) -> str:
    """Return run / suspend / wait for one execution or event mapping."""
    event_type = str(record.get("type") or "")
    if event_type in WAKE_TYPES:
        return RUN
    if event_type == "human.wait":
        return WAIT
    if event_type == "execution.suspend":
        return SUSPEND
    reason = record.get("wait_reason")
    reason_text = None if reason is None else str(reason)
    if reason_text == WAITING_HUMAN:
        return WAIT
    if reason_text in IO_REASONS:
        return SUSPEND
    if reason_text in WORKER_REASONS:
        return RUN
    state = str(record.get("state") or "")
    if state in {"ready", "running"}:
        return RUN
    if state in {"waiting", "suspended"}:
        return SUSPEND if reason_text != WAITING_HUMAN else WAIT
    return SUSPEND


def select(
    executions: Sequence[Mapping[str, Any]],
    *,
    limit: int = 1,
) -> list[dict[str, Any]]:
    """Highest-priority records whose decision is run."""
    if limit < 1:
        return []
    runnable = [dict(item) for item in executions if decide(item) == RUN]
    runnable.sort(key=lambda item: int(item.get("priority") or 0), reverse=True)
    return runnable[:limit]


class AgentScheduler:
    """Callable scheduler Host can inject into the event loop."""

    def decide(self, record: Mapping[str, Any]) -> str:
        return decide(record)

    def select(
        self,
        executions: Sequence[Mapping[str, Any]],
        *,
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        return select(executions, limit=limit)
