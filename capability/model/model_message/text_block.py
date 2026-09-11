# -*- coding: utf-8 -*-
"""Plain text content block plugin."""

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from kernel.compose.capability.capability import Capability


class TextBlockCapability(Capability):
    name = "model.message.text"
    version = "1.0"
    kind = "model.message"
    provides = ("model.message.text",)


PLUGIN_NAME = "model.message.text"
PLUGIN_VERSION = "1.0"


def _generate_id() -> str:
    return uuid4().hex


@dataclass
class TextBlock:
    """Plain text content."""

    text: str
    type: Literal["text"] = "text"
    id: str = field(default_factory=_generate_id)


__all__ = ["TextBlock"]
