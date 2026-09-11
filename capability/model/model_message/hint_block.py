# -*- coding: utf-8 -*-
"""Collaboration hints in agent reasoning and action loop."""

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from kernel.compose.capability.capability import Capability


class HintBlockCapability(Capability):
    name = "model.message.hint"
    version = "1.0"
    kind = "model.message"
    provides = ("model.message.hint",)


PLUGIN_NAME = "model.message.hint"
PLUGIN_VERSION = "1.0"


def _generate_id() -> str:
    return uuid4().hex


@dataclass
class HintBlock:
    """Text or multimodal collaboration hints in agent reasoning and action loop."""

    hint: str | list[Any]
    type: Literal["hint"] = "hint"
    id: str = field(default_factory=_generate_id)
    source: str | None = None


__all__ = ["HintBlock"]
