"""Validate the trusted boundary between a frontend and the gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ProtocolError(ValueError):
    """A request did not satisfy the versioned connection contract."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class ActionRequest:
    """A validated action request from one frontend."""

    version: int
    request_id: str
    action: str
    payload: dict[str, Any]


SUPPORTED_ACTIONS = frozenset(
    {
        "chat.send",
        "process.send",
        "process.create",
        "environment.load",
        "model.configure",
        "command.execute",
    }
)


def parse_request(value: Any) -> ActionRequest:
    """Validate one JSON-decoded action request."""

    if not isinstance(value, dict):
        raise ProtocolError("invalid_request", "Action request must be an object")
    unknown = set(value) - {"version", "request_id", "action", "payload"}
    if unknown:
        raise ProtocolError("invalid_request", f"Unknown request fields: {sorted(unknown)}")
    if value.get("version") != 1:
        raise ProtocolError("unsupported_version", "Action request version must be 1")

    request_id = value.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        raise ProtocolError("invalid_request_id", "Action request needs a non-empty request_id")

    action = value.get("action")
    if not isinstance(action, str) or action not in SUPPORTED_ACTIONS:
        raise ProtocolError("unsupported_action", f"Unsupported action: {action!r}")

    payload = value.get("payload")
    if not isinstance(payload, dict):
        raise ProtocolError("invalid_payload", "Action payload must be an object")

    return ActionRequest(
        version=1,
        request_id=request_id.strip(),
        action=action,
        payload=payload,
    )
