# -*- coding: utf-8 -*-
"""Tool execution result and result status plugin."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from kernel.compose.capability.capability import Capability


class ToolResultCapability(Capability):
    name = "model.message.tool_result"
    version = "1.0"
    kind = "model.message"
    provides = ("model.message.tool_result",)


PLUGIN_NAME = "model.message.tool_result"
PLUGIN_VERSION = "1.0"


class ToolResultState(StrEnum):
    """Tool execution result state machine."""

    SUCCESS = "success"
    ERROR = "error"
    INTERRUPTED = "interrupted"
    DENIED = "denied"
    RUNNING = "running"


@dataclass
class ToolResultBlock:
    """Text or multimodal results produced by tool execution."""

    id: str
    name: str
    output: str | list[Any]
    type: Literal["tool_result"] = "tool_result"
    state: ToolResultState = ToolResultState.RUNNING
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["ToolResultBlock", "ToolResultState"]
