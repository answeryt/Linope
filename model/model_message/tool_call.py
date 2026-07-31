# -*- coding: utf-8 -*-
"""工具调用及权限状态插件。"""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolCallState(StrEnum):
    """工具调用状态机。"""

    PENDING = "pending"
    ASKING = "asking"
    ALLOWED = "allowed"
    SUBMITTED = "submitted"
    FINISHED = "finished"


class ToolCallBlock(BaseModel):
    """工具调用、原始参数、权限状态及外部注入的建议规则。"""

    model_config = ConfigDict(use_enum_values=True)

    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    input: str
    state: ToolCallState = ToolCallState.PENDING
    suggested_rules: list[Any] = Field(default_factory=list)


__all__ = ["ToolCallBlock", "ToolCallState"]
