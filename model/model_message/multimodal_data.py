# -*- coding: utf-8 -*-
"""Multimodal data plugin for images, audio, video, and files."""

from typing import Literal
from uuid import uuid4

from pydantic import AnyUrl, BaseModel, Field, field_serializer


def _generate_id() -> str:
    return uuid4().hex


class Base64Source(BaseModel):
    """Binary data source represented by an embedded Base64 string."""

    type: Literal["base64"] = "base64"
    data: str
    media_type: str


class URLSource(BaseModel):
    """Binary data source represented by a URL."""

    type: Literal["url"] = "url"
    url: AnyUrl
    media_type: str

    @field_serializer("url")
    def serialize_url(self, url: AnyUrl) -> str:
        """Serialize a Pydantic URL to a regular string."""
        return str(url)


class DataBlock(BaseModel):
    """Multimodal data for images, audio, video, and files."""

    type: Literal["data"] = "data"
    id: str = Field(default_factory=_generate_id)
    source: Base64Source | URLSource
    name: str | None = None


__all__ = ["Base64Source", "DataBlock", "URLSource"]
