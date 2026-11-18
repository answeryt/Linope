"""Small validators for untrusted semantic action payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from connection.protocol.request import ProtocolError


def required_text(payload: Mapping[str, Any], name: str) -> str:
    """Read a required non-empty string."""

    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError("invalid_payload", f"{name} must be a non-empty string")
    return value.strip()


def optional_text(payload: Mapping[str, Any], name: str) -> str | None:
    """Read an optional non-empty string."""

    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError("invalid_payload", f"{name} must be a non-empty string when provided")
    return value.strip()


def positive_integer(payload: Mapping[str, Any], name: str) -> int | None:
    """Read an optional positive integer."""

    value = payload.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProtocolError("invalid_payload", f"{name} must be a positive integer")
    return value


def positive_number(payload: Mapping[str, Any], name: str) -> float | None:
    """Read an optional positive number."""

    value = payload.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ProtocolError("invalid_payload", f"{name} must be a positive number")
    return float(value)


def string_list(payload: Mapping[str, Any], name: str) -> tuple[str, ...]:
    """Read an optional list of non-empty strings."""

    value = payload.get(name, [])
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ProtocolError("invalid_payload", f"{name} must be an array of strings")
    result = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    if len(result) != len(value):
        raise ProtocolError("invalid_payload", f"{name} must contain only non-empty strings")
    return result


def changes(payload: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Read repeated capability changes as topic/value records."""

    value = payload.get("changes", [])
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ProtocolError("invalid_payload", "changes must be an array")

    result: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ProtocolError("invalid_payload", "Each change must be an object")
        topic = item.get("topic")
        change_value = item.get("value")
        if (
            not isinstance(topic, str)
            or not topic.strip()
            or not isinstance(change_value, str)
        ):
            raise ProtocolError("invalid_payload", "Each change needs topic and string value")
        result.append((topic.strip(), change_value))
    return tuple(result)


def resource_bindings(payload: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Read extra resource bindings as kind/identity records."""

    value = payload.get("with", [])
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ProtocolError("invalid_payload", "with must be an array")

    result: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ProtocolError("invalid_payload", "Each with entry must be an object")
        kind = item.get("kind")
        identity = item.get("identity")
        if (
            not isinstance(kind, str)
            or not kind.strip()
            or not isinstance(identity, str)
            or not identity.strip()
        ):
            raise ProtocolError("invalid_payload", "Each with entry needs kind and identity")
        result.append((kind.strip(), identity.strip()))
    return tuple(result)
