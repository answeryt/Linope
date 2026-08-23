# -*- coding: utf-8 -*-
"""Serializable request that creates or resumes one logical process."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_process_activation"
PLUGIN_VERSION = "1.0"


def new_activation_id() -> str:
    return uuid4().hex


def build_activation(
    process_type: str,
    input: Any,
    *,
    process_id: str | None = None,
    activation_id: str | None = None,
    reason: str = "input",
    correlation_id: str | None = None,
    caused_by: str | None = None,
    priority: int = 0,
    **fields: Any,
) -> dict[str, Any]:
    """Build the portable envelope accepted by a process-driven service."""
    if not process_type:
        raise ValueError("process_type is required")
    aid = activation_id or new_activation_id()
    record = {
        "activation_id": aid,
        "process_id": process_id,
        "process_type": process_type,
        "input": input,
        "reason": reason,
        "correlation_id": correlation_id or aid,
        "caused_by": caused_by,
        "priority": int(priority),
    }
    record.update(fields)
    return record


def normalize_activation(
    payload: Mapping[str, Any] | str,
    *,
    default_process_type: str = "default",
    message_id: str | None = None,
) -> dict[str, Any]:
    """Normalize external input without transporting a live process object."""
    if isinstance(payload, str):
        return build_activation(
            default_process_type,
            {"user_message": payload},
            activation_id=message_id,
        )
    record = dict(payload)
    process_type = str(record.pop("process_type", default_process_type) or "")
    process_id = record.pop("process_id", None)
    activation_id = record.pop("activation_id", None) or message_id
    input_value = record.pop("input", record)
    return build_activation(
        process_type,
        input_value,
        process_id=process_id,
        activation_id=activation_id,
    )
