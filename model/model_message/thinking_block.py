# -*- coding: utf-8 -*-
"""模型推理内容块插件。"""

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _generate_id() -> str:
    return uuid4().hex


class ThinkingBlock(BaseModel):
    """模型推理内容，允许保留模型提供商的扩展字段。"""

    model_config = ConfigDict(extra="allow")

    type: Literal["thinking"] = "thinking"
    thinking: str
    id: str = Field(default_factory=_generate_id)


__all__ = ["ThinkingBlock"]
