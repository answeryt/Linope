# -*- coding: utf-8 -*-
"""Tool call and permission state plugin."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from kernel.compose.capability.capability import Capability


class ToolCallCapability(Capability):
    name = "model.message.tool_call"
    version = "1.0"
    kind = "model.message"
    provides = ("model.message.tool_call",)


PLUGIN_NAME = "model.message.tool_call"
PLUGIN_VERSION = "1.0"


class ToolCallState(StrEnum):
    """Tool call state machine."""

    PENDING = "pending"
    ASKING = "asking"
    ALLOWED = "allowed"
    SUBMITTED = "submitted"
    FINISHED = "finished"


@dataclass
class ToolCallBlock:
    """Tool call, raw arguments, permission state, and externally injected suggested rules."""

    id: str
    name: str
    input: str
    type: Literal["tool_call"] = "tool_call"
    state: ToolCallState = ToolCallState.PENDING
    suggested_rules: list[Any] = field(default_factory=list)


__all__ = ["ToolCallBlock", "ToolCallState"]
