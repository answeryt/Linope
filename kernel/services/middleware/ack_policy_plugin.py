# -*- coding: utf-8 -*-
"""Acknowledgement policy for long-running agent tasks.

Agent loops must not ack on consume. Default is nack-on-error: ack after
a successful loop, nack retryable failures, reject invalid payloads.
"""

from __future__ import annotations

from enum import Enum


PLUGIN_NAME = "kernel_ack_policy"
PLUGIN_VERSION = "1.0"


class AckPolicy(str, Enum):
    ACK_FIRST = "ack_first"
    """Ack as soon as the task is pulled. Unsafe for agent loops."""

    ACK = "ack"
    """Ack after the loop returns, even if it raised."""

    REJECT_ON_ERROR = "reject_on_error"
    """Ack on success; reject on unhandled errors (no retry)."""

    NACK_ON_ERROR = "nack_on_error"
    """Ack on success; nack on unhandled errors so another worker can retry."""

    MANUAL = "manual"
    """Do not ack/nack/reject automatically."""


DEFAULT_AGENT_POLICY = AckPolicy.NACK_ON_ERROR
