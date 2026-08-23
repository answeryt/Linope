# -*- coding: utf-8 -*-
"""Ack after one Process activation finishes.

Default policy nack_on_error. Activation mappings may carry ack/nack/reject
callables from the stream subscriber. Invalid payloads are rejected.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from typing import Any


PLUGIN_NAME = "kernel_ack_middleware"
PLUGIN_VERSION = "1.0"

ACK_FIRST = "ack_first"
ACK = "ack"
REJECT_ON_ERROR = "reject_on_error"
NACK_ON_ERROR = "nack_on_error"
MANUAL = "manual"


class ProcessActivationInvalid(ValueError):
    """Process activation cannot be handled."""


async def _invoke(method: Any) -> None:
    if method is None:
        return
    result = method() if callable(method) else method
    if hasattr(result, "__await__"):
        await result


class AckMiddleware:
    """Confirm a stream message after Process activation."""

    def __init__(
        self,
        *,
        ack_policy: str = NACK_ON_ERROR,
        logger: logging.Logger | None = None,
    ) -> None:
        self.ack_policy = str(getattr(ack_policy, "value", ack_policy))
        self.logger = logger or logging.getLogger(PLUGIN_NAME)

    async def consume_scope(
        self,
        call_next: Callable[..., Awaitable[Any]],
        task: Mapping[str, Any],
    ) -> Any:
        if self.ack_policy == MANUAL:
            return await call_next(task)
        if self.ack_policy == ACK_FIRST:
            await _invoke(task.get("ack"))
            return await call_next(task)
        try:
            result = await call_next(task)
        except Exception as exc:
            if type(exc).__name__ in {
                "AgentTaskInvalid",
                "ProcessActivationInvalid",
            }:
                await _invoke(task.get("reject"))
            elif self.ack_policy == REJECT_ON_ERROR:
                await _invoke(task.get("reject"))
            elif self.ack_policy == NACK_ON_ERROR:
                await _invoke(task.get("nack"))
            elif self.ack_policy == ACK:
                await _invoke(task.get("ack"))
            raise
        else:
            await _invoke(task.get("ack"))
            return result
