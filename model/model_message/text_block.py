# -*- coding: utf-8 -*-
"""Plain text content block plugin."""

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _generate_id() -> str:
    return uuid4().hex


class TextBlock(BaseModel):
    """Plain text content."""

    type: Literal["text"] = "text"
    text: str
    id: str = Field(default_factory=_generate_id)


__all__ = ["TextBlock"]
