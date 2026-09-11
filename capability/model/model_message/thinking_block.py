# -*- coding: utf-8 -*-
"""Model reasoning content block plugin."""

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from kernel.compose.capability.capability import Capability


class ThinkingBlockCapability(Capability):
    name = "model.message.thinking"
    version = "1.0"
    kind = "model.message"
    provides = ("model.message.thinking",)


PLUGIN_NAME = "model.message.thinking"
PLUGIN_VERSION = "1.0"


def _generate_id() -> str:
    return uuid4().hex


@dataclass
class ThinkingBlock:
    """Model reasoning content, allowing the model provider to preserve extended fields."""

    thinking: str
    type: Literal["thinking"] = "thinking"
    id: str = field(default_factory=_generate_id)
    extra: dict[str, Any] = field(default_factory=dict)


__all__ = ["ThinkingBlock"]
