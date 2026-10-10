# -*- coding: utf-8 -*-
"""Content blocks used when assembling model messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4


def _generate_id() -> str:
    return uuid4().hex


@dataclass
class TextBlock:
    """Plain text content."""

    text: str
    type: Literal["text"] = "text"
    id: str = field(default_factory=_generate_id)


@dataclass
class ThinkingBlock:
    """Model reasoning content; extra keeps provider-specific fields."""

    thinking: str
    type: Literal["thinking"] = "thinking"
    id: str = field(default_factory=_generate_id)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class HintBlock:
    """Collaboration hints in the agent reasoning and action loop."""

    hint: str | list[Any]
    type: Literal["hint"] = "hint"
    id: str = field(default_factory=_generate_id)
    source: str | None = None


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


class ToolCallState(StrEnum):
    """Tool call state machine."""

    PENDING = "pending"
    ASKING = "asking"
    ALLOWED = "allowed"
    SUBMITTED = "submitted"
    FINISHED = "finished"


@dataclass
class ToolCallBlock:
    """Tool call, raw arguments, permission state, and suggested rules."""

    id: str
    name: str
    input: str
    type: Literal["tool_call"] = "tool_call"
    state: ToolCallState = ToolCallState.PENDING
    suggested_rules: list[Any] = field(default_factory=list)


class ToolResultState(StrEnum):
    """Tool execution result state machine."""

    SUCCESS = "success"
    ERROR = "error"
    INTERRUPTED = "interrupted"
    DENIED = "denied"
    RUNNING = "running"


@dataclass
class ToolResultBlock:
    """Text or multimodal results produced by tool execution."""

    id: str
    name: str
    output: str | list[Any]
    type: Literal["tool_result"] = "tool_result"
    state: ToolResultState = ToolResultState.RUNNING
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "Base64Source",
    "DataBlock",
    "HintBlock",
    "TextBlock",
    "ThinkingBlock",
    "ToolCallBlock",
    "ToolCallState",
    "ToolResultBlock",
    "ToolResultState",
    "URLSource",
]
