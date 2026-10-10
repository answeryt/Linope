"""Normalize outside input into one serializable ServiceRequest."""

from __future__ import annotations

from typing import Any

from kernel.services.contracts import ServiceRequest


def normalize_request(
    raw: ServiceRequest | dict[str, Any] | str,
    *,
    kind: str = "",
    role: str = "",
) -> ServiceRequest:
    """Accept a request, a mailbox message, or plain text with a kind."""
    if isinstance(raw, ServiceRequest):
        return raw
    if isinstance(raw, dict):
        return ServiceRequest.from_message(raw, role=role)
    if not kind:
        raise ValueError("纯文本请求必须说明资源种类")
    return ServiceRequest(kind=kind, body=raw, role=role)
