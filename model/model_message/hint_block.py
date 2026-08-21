# -*- coding: utf-8 -*-
"""Collaboration hints in agent reasoning and action loop."""

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .multimodal_data import DataBlock
from .text_block import TextBlock


def _generate_id() -> str:
    return uuid4().hex


class HintBlock(BaseModel):
    """Text or multimodal collaboration hints in agent reasoning and action loop."""

    type: Literal["hint"] = "hint"
    hint: str | list[TextBlock | DataBlock]
    id: str = Field(default_factory=_generate_id)
    source: str | None = None


__all__ = ["HintBlock"]
