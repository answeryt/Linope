# -*- coding: utf-8 -*-
"""Multimodal data plugin for images, audio, video, and files."""

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from kernel.compose.capability.capability import Capability


class MultimodalDataCapability(Capability):
    name = "model.message.multimodal"
    version = "1.0"
    kind = "model.message"
    provides = ("model.message.multimodal",)


PLUGIN_NAME = "model.message.multimodal"
PLUGIN_VERSION = "1.0"


def _generate_id() -> str:
    return uuid4().hex


@dataclass
class Base64Source:
    """Binary data source represented by an embedded Base64 string."""

    data: str
    media_type: str
    type: Literal["base64"] = "base64"


@dataclass
class URLSource:
    """Binary data source represented by a URL."""

    url: str
    media_type: str
    type: Literal["url"] = "url"


@dataclass
class DataBlock:
    """Multimodal data for images, audio, video, and files."""

    source: Base64Source | URLSource
    type: Literal["data"] = "data"
    id: str = field(default_factory=_generate_id)
    name: str | None = None


__all__ = ["Base64Source", "DataBlock", "URLSource"]
