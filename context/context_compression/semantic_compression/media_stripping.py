"""Multimodal image replacement and historical-media stripping."""

from __future__ import annotations

from typing import Any, Callable


IMAGE_TYPES = frozenset({"image", "image_url", "input_image"})


def replace_image_parts(
    messages: list[dict[str, Any]],
    *,
    should_replace: Callable[[int, dict[str, Any]], bool],
    placeholder: str = "[Attached image — stripped after compression]",
    stale_sidecar_keys: tuple[str, ...] = ("api_content",),
) -> list[dict[str, Any]]:
    """Replace selected image parts with text placeholders."""
    result = list(messages)
    changed = False
    for index, message in enumerate(messages):
        content = message.get("content")
        if not isinstance(content, list) or not should_replace(index, message):
            continue
        if not any(isinstance(part, dict) and part.get("type") in IMAGE_TYPES for part in content):
            continue
        parts = [
            {"type": "text", "text": placeholder}
            if isinstance(part, dict) and part.get("type") in IMAGE_TYPES
            else part
            for part in content
        ]
        replacement = {**message, "content": parts}
        for key in stale_sidecar_keys:
            replacement.pop(key, None)
        result[index] = replacement
        changed = True
    return result if changed else messages


def strip_historical_media(
    messages: list[dict[str, Any]],
    *,
    placeholder: str = "[Attached image — stripped after compression]",
    stale_sidecar_keys: tuple[str, ...] = ("api_content",),
) -> list[dict[str, Any]]:
    """Strip images before the newest image-bearing user message."""
    anchor = -1
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        content = message.get("content")
        if (
            message.get("role") == "user"
            and isinstance(content, list)
            and any(isinstance(part, dict) and part.get("type") in IMAGE_TYPES for part in content)
        ):
            anchor = index
            break
    if anchor <= 0:
        return messages
    return replace_image_parts(
        messages,
        should_replace=lambda index, _message: index < anchor,
        placeholder=placeholder,
        stale_sidecar_keys=stale_sidecar_keys,
    )
