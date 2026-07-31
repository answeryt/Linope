"""Serialize transcript turns for a summarizer without owning sanitization."""

from collections.abc import Callable
from typing import Any


def serialize_turns(
    messages: list[dict[str, Any]],
    *,
    redactor: Callable[[str], str],
    think_stripper: Callable[[str], str],
    image_labeler: Callable[[dict[str, Any]], str],
    content_max_chars: int = 6_000,
    content_head_chars: int = 4_000,
    content_tail_chars: int = 1_500,
    tool_args_max_chars: int = 1_500,
    tool_args_head_chars: int = 1_200,
) -> str:
    """Produce labeled text while injecting all policy-sensitive transforms."""
    if min(
        content_max_chars,
        content_head_chars,
        content_tail_chars,
        tool_args_max_chars,
        tool_args_head_chars,
    ) < 0:
        raise ValueError("serialization limits must be non-negative")

    def truncate(text: str, maximum: int, head: int, tail: int = 0) -> str:
        if len(text) <= maximum:
            return text
        if tail:
            return text[:head] + "\n...[truncated]...\n" + text[-tail:]
        return text[:head] + "..."

    def content_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if not isinstance(value, list):
            return "" if value is None else str(value)
        parts: list[str] = []
        for part in value:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                part_type = part.get("type")
                if part_type in {"text", "input_text"}:
                    parts.append(str(part.get("text") or ""))
                elif part_type in {"image", "image_url", "input_image"}:
                    parts.append(image_labeler(part))
                else:
                    parts.append(f"[{part_type or 'attachment'}]")
        return "\n".join(parts)

    output: list[str] = []
    for message in messages:
        role = str(message.get("role") or "unknown")
        content = redactor(content_text(message.get("content")))
        if role == "assistant":
            content = think_stripper(content)
        content = truncate(
            content, content_max_chars, content_head_chars, content_tail_chars
        )

        if role == "tool":
            output.append(
                f"[TOOL RESULT {message.get('tool_call_id', '')}]: {content}"
            )
            continue

        if role == "assistant":
            calls: list[str] = []
            for call in message.get("tool_calls") or []:
                if isinstance(call, dict):
                    function = call.get("function") or {}
                    name = function.get("name") or "?"
                    arguments = redactor(str(function.get("arguments") or ""))
                else:
                    function = getattr(call, "function", None)
                    name = getattr(function, "name", "?") if function else "?"
                    arguments = "..."
                arguments = truncate(
                    arguments, tool_args_max_chars, tool_args_head_chars
                )
                calls.append(f"  {name}({arguments})")
            if calls:
                content += "\n[Tool calls:\n" + "\n".join(calls) + "\n]"
            output.append(f"[ASSISTANT]: {content}")
            continue

        output.append(f"[{role.upper()}]: {content}")

    return "\n\n".join(output)
