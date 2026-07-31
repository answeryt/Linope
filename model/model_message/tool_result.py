# -*- coding: utf-8 -*-
"""Tool execution result and result status plugin."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .multimodal_data import DataBlock
from .text_block import TextBlock


class ToolResultState(StrEnum):
    """Tool execution result state machine."""

    SUCCESS = "success"
    ERROR = "error"
    INTERRUPTED = "interrupted"
    DENIED = "denied"
    RUNNING = "running"


class ToolResultBlock(BaseModel):
    """Text or multimodal results produced by tool execution."""

    model_config = ConfigDict(use_enum_values=True)

    type: Literal["tool_result"] = "tool_result"
    id: str
    name: str
    output: str | list[TextBlock | DataBlock]
    state: ToolResultState = ToolResultState.RUNNING
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = ["ToolResultBlock", "ToolResultState"]
