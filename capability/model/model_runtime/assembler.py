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
    """Assemble text and one tool call per index. Truncation drops every call."""

    def __init__(self) -> None:
        self._text: list[str] = []
        self._reasoning: list[str] = []
        self._tools: dict[int, dict[str, Any]] = {}
        self._finish_reason = "stop"
        self._usage: dict[str, Any] | None = None
        self._errors: list[str] = []

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
            index = int(part.get("index") or 0)
            slot = self._tools.setdefault(
                index,
                {"id": "", "name": "", "arguments": "" if kind == "tool-call-delta" else None},
            )
            if part.get("id"):
                slot["id"] = str(part["id"])
            if part.get("name"):
                slot["name"] = str(part["name"])
            if kind == "tool-call":
                slot["arguments"] = part.get("arguments")
            else:
                fragment = part.get("arguments")
                if fragment:
                    previous = slot["arguments"] if isinstance(slot["arguments"], str) else ""
                    slot["arguments"] = previous + str(fragment)
        elif kind == "finish":
            self._finish_reason = str(part.get("reason") or "stop")
        elif kind == "usage" and isinstance(part.get("usage"), dict):
            merged = dict(self._usage or {})
            merged.update(part["usage"])
            self._usage = merged

    def finish(self) -> ModelTurn:
        blocks: list = []
        if self._text:
            blocks.append(TextBlock(text="".join(self._text)))
        if self._reasoning:
            blocks.append(ReasoningBlock(text="".join(self._reasoning)))
        if self._tools and self._finish_reason not in {"max-tokens", "length"}:
            for index in sorted(self._tools):
                slot = self._tools[index]
                if not slot["name"]:
                    self._errors.append(f"tool call {index} has no name")
                    continue
                arguments = slot["arguments"]
                if isinstance(arguments, str) and arguments:
                    import json
                    try:
                        json.loads(arguments)
                    except json.JSONDecodeError:
                        self._errors.append(f"tool call {index} arguments are not JSON")
                blocks.append(
                    ToolCallBlock(
                        name=slot["name"],
                        arguments=arguments,
                        id=slot["id"],
                        index=index,
                    )
                )
        if self._errors:
            blocks.append(TextBlock(text="; ".join(self._errors)))
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
