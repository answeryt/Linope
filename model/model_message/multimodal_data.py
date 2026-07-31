# -*- coding: utf-8 -*-
"""图片、音频、视频及文件等多模态数据插件。"""

from typing import Literal
from uuid import uuid4

from pydantic import AnyUrl, BaseModel, Field, field_serializer


def _generate_id() -> str:
    return uuid4().hex


class Base64Source(BaseModel):
    """以内嵌 Base64 字符串表示的二进制数据来源。"""

    type: Literal["base64"] = "base64"
    data: str
    media_type: str


class URLSource(BaseModel):
    """以 URL 表示的二进制数据来源。"""

    type: Literal["url"] = "url"
    url: AnyUrl
    media_type: str

    @field_serializer("url")
    def serialize_url(self, url: AnyUrl) -> str:
        """将 Pydantic URL 序列化为普通字符串。"""
        return str(url)


class DataBlock(BaseModel):
    """图片、音频、视频及文件等多模态数据。"""

    type: Literal["data"] = "data"
    id: str = Field(default_factory=_generate_id)
    source: Base64Source | URLSource
    name: str | None = None


__all__ = ["Base64Source", "DataBlock", "URLSource"]
