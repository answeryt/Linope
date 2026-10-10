"""Incrementally assemble provider-neutral model output blocks."""

from __future__ import annotations

from typing import Any

from capability.model.model_runtime.blocks import (
    ModelTurn,
    ReasoningBlock,
    TextBlock,
    ToolCallBlock,
)


class BlockAssembler:
    """Assemble text and at most one tool call for a model step."""

    def __init__(self) -> None:
        self._text: list[str] = []
        self._reasoning: list[str] = []
        self._tool_name = ""
        self._tool_arguments: Any = None
        self._has_tool = False
        self._finish_reason = "stop"
        self._usage: dict[str, Any] | None = None

    def push(self, part: Any) -> None:
        if not isinstance(part, dict):
            if part:
                self._text.append(str(part))
            return
        kind = part.get("type")
        if kind in {"text", "text-delta"}:
            text = part.get("text")
            if text:
                self._text.append(str(text))
        elif kind in {"reasoning", "reasoning-delta"}:
            text = part.get("text")
            if text:
                self._reasoning.append(str(text))
        elif kind in {"tool-call", "tool-call-delta"}:
            self._has_tool = True
            if part.get("name"):
                self._tool_name = str(part["name"])
            if kind == "tool-call":
                self._tool_arguments = part.get("arguments")
            else:
                fragment = part.get("arguments")
                if fragment:
                    previous = (
                        self._tool_arguments
                        if isinstance(self._tool_arguments, str)
                        else ""
                    )
                    self._tool_arguments = previous + str(fragment)
        elif kind == "finish":
            self._finish_reason = str(part.get("reason") or "stop")
        elif kind == "usage" and isinstance(part.get("usage"), dict):
            self._usage = dict(part["usage"])

    def finish(self) -> ModelTurn:
        blocks: list = []
        if self._text:
            blocks.append(TextBlock(text="".join(self._text)))
        if self._reasoning:
            blocks.append(ReasoningBlock(text="".join(self._reasoning)))
        if self._has_tool and self._finish_reason not in {"max-tokens", "length"}:
            blocks.append(
                ToolCallBlock(
                    name=self._tool_name,
                    arguments=self._tool_arguments,
                )
            )
        return ModelTurn(
            blocks=tuple(blocks),
            finish_reason=self._finish_reason,
            usage=self._usage,
        )


def assemble(parts: list[Any]) -> ModelTurn:
    assembler = BlockAssembler()
    for part in parts:
        assembler.push(part)
    return assembler.finish()
