"""Provider-neutral model output blocks.

Model prose, reasoning, tool requests, and tool results are deliberately
different values.  The terminal may inspect text blocks for its legacy
command envelope, but it must never scan reasoning or result blocks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class TextBlock:
    type: Literal["text"] = "text"
    text: str = ""


@dataclass(frozen=True)
class ReasoningBlock:
    type: Literal["reasoning"] = "reasoning"
    text: str = ""


@dataclass(frozen=True)
class ToolCallBlock:
    type: Literal["tool-call"] = "tool-call"
    name: str = ""
    arguments: Any = None


@dataclass(frozen=True)
class ToolResultBlock:
    type: Literal["tool-result"] = "tool-result"
    request_id: str = ""
    output: Any = None
    is_error: bool = False


Block = TextBlock | ReasoningBlock | ToolCallBlock | ToolResultBlock


@dataclass(frozen=True)
class ModelTurn:
    """One provider-neutral model response."""

    blocks: tuple[Block, ...] = ()
    finish_reason: str = "stop"
    usage: dict[str, Any] | None = None

    def text(self) -> str:
        return "\n".join(
            block.text
            for block in self.blocks
            if isinstance(block, TextBlock) and block.text
        )

    def tool_calls(self) -> tuple[ToolCallBlock, ...]:
        return tuple(
            block for block in self.blocks if isinstance(block, ToolCallBlock)
        )

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "type": "model_turn",
            "blocks": [asdict(block) for block in self.blocks],
            "finish_reason": self.finish_reason,
        }
        if self.usage is not None:
            payload["usage"] = dict(self.usage)
        return payload


def block_from_payload(raw: Any) -> Block | None:
    if not isinstance(raw, dict):
        return None
    kind = raw.get("type")
    if kind == "text":
        return TextBlock(text=str(raw.get("text") or ""))
    if kind == "reasoning":
        return ReasoningBlock(text=str(raw.get("text") or ""))
    if kind == "tool-call":
        return ToolCallBlock(
            name=str(raw.get("name") or ""),
            arguments=raw.get("arguments"),
        )
    if kind == "tool-result":
        return ToolResultBlock(
            request_id=str(raw.get("request_id") or ""),
            output=raw.get("output"),
            is_error=bool(raw.get("is_error")),
        )
    return None


def turn_from_payload(raw: Any) -> ModelTurn | None:
    if not isinstance(raw, dict) or raw.get("type") != "model_turn":
        return None
    blocks = tuple(
        block
        for item in raw.get("blocks") or ()
        if (block := block_from_payload(item)) is not None
    )
    usage = raw.get("usage")
    return ModelTurn(
        blocks=blocks,
        finish_reason=str(raw.get("finish_reason") or "stop"),
        usage=dict(usage) if isinstance(usage, dict) else None,
    )
