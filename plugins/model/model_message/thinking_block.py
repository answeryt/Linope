# -*- coding: utf-8 -*-
"""Model reasoning content block plugin."""

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _generate_id() -> str:
    return uuid4().hex


class ThinkingBlock(BaseModel):
    """Model reasoning content, allowing the model provider to preserve extended fields."""

    model_config = ConfigDict(extra="allow")

    type: Literal["thinking"] = "thinking"
    thinking: str
    id: str = Field(default_factory=_generate_id)


__all__ = ["ThinkingBlock"]
