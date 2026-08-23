# -*- coding: utf-8 -*-
"""Log one agent task by task_id. Failures must not swallow the exception."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any


PLUGIN_NAME = "kernel_logging"
PLUGIN_VERSION = "1.0"


class LoggingMiddleware:
    """Record receive / processed / error around the agent loop."""

    def __init__(self, *, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(PLUGIN_NAME)

    def _extra(self, task: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "task_id": task.get("task_id"),
            "session_id": task.get("session_id"),
            "message_id": task.get("message_id"),
        }

    async def consume_scope(
        self,
        call_next: Callable[..., Awaitable[Any]],
        task: Mapping[str, Any],
    ) -> Any:
        extra = self._extra(task)
        self.logger.info("agent task received", extra=extra)
        try:
            result = await call_next(task)
        except Exception as exc:
            self.logger.error(
                "%s: %s",
                type(exc).__name__,
                exc,
                extra=extra,
                exc_info=exc,
            )
            raise
        self.logger.info("agent task processed", extra=extra)
        return result
