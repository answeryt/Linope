# -*- coding: utf-8 -*-
"""普通文本内容块插件。"""

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _generate_id() -> str:
    return uuid4().hex


class TextBlock(BaseModel):
    """普通文本内容。"""

    type: Literal["text"] = "text"
    text: str
    id: str = Field(default_factory=_generate_id)


__all__ = ["TextBlock"]
