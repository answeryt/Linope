"""Roles on text that travels to or from a model."""

from __future__ import annotations

from enum import StrEnum


class MessageRole(StrEnum):
    """Who spoke. This is not the model facility and not a service member role."""

    USER = "user_msg"
    TOOL = "tool_msg"
    MODEL = "model_msg"
    SYSTEM = "system_msg"


def message(role: MessageRole, content: str) -> dict[str, str]:
    """One message body. ``model_msg`` is the model speaking, not the model lease."""
    return {"role": role.value, "content": content}
