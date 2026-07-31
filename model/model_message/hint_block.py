# -*- coding: utf-8 -*-
"""智能体推理与行动循环中的协作提示插件。"""

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .multimodal_data import DataBlock
from .text_block import TextBlock


def _generate_id() -> str:
    return uuid4().hex


class HintBlock(BaseModel):
    """智能体推理与行动循环中的文本或多模态协作提示。"""

    type: Literal["hint"] = "hint"
    hint: str | list[TextBlock | DataBlock]
    id: str = Field(default_factory=_generate_id)
    source: str | None = None


__all__ = ["HintBlock"]
