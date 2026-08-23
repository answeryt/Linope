# -*- coding: utf-8 -*-
"""External envelope for creating or resuming a logical Process."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_activation_envelope"
PLUGIN_VERSION = "1.0"


def normalize_activation(
    payload: Mapping[str, Any] | str,
    *,
    default_process_type: str = "default",
    message_id: str | None = None,
) -> dict[str, Any]:
    """Build a portable activation; live Process objects never cross ingress."""
    raw = {"input": {"user_message": payload}} if isinstance(payload, str) else dict(payload)
    process_type = str(raw.pop("process_type", default_process_type) or "")
    if not process_type:
        raise ValueError("process_type is required")
    activation_id = str(raw.pop("activation_id", None) or message_id or uuid4().hex)
    input_value = raw.pop("input", raw)
    return {
        "activation_id": activation_id,
        "process_id": raw.pop("process_id", None),
        "process_type": process_type,
        "input": input_value,
        "reason": raw.pop("reason", "input"),
        "correlation_id": raw.pop("correlation_id", activation_id),
        "caused_by": raw.pop("caused_by", None),
        "priority": int(raw.pop("priority", 0)),
    }
