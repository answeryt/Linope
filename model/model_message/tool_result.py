# -*- coding: utf-8 -*-
"""工具执行结果及结果状态插件。"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .multimodal_data import DataBlock
from .text_block import TextBlock


class ToolResultState(StrEnum):
    """工具执行结果状态机。"""

    SUCCESS = "success"
    ERROR = "error"
    INTERRUPTED = "interrupted"
    DENIED = "denied"
    RUNNING = "running"


class ToolResultBlock(BaseModel):
    """工具执行产生的文本或多模态结果。"""

    model_config = ConfigDict(use_enum_values=True)

    type: Literal["tool_result"] = "tool_result"
    id: str
    name: str
    output: str | list[TextBlock | DataBlock]
    state: ToolResultState = ToolResultState.RUNNING
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = ["ToolResultBlock", "ToolResultState"]
