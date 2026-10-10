# -*- coding: utf-8 -*-
"""Rough token estimators for text, images, messages, and tool schemas."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


DEFAULT_IMAGE_TOKEN_COST = 1500

TextEstimator = Callable[[str], int]
ImageEstimator = Callable[[dict], int]


def estimate_text_tokens_rough(text: str) -> int:
    if not text:
        return 0
    text = str(text)
    if text.isascii():
        return (len(text) + 3) // 4

    dense = sum(1 for char in text if _is_cjk_token_dense_char(char))
    if not dense:
        return (len(text) + 3) // 4
    sparse = len(text) - dense
    return dense + ((sparse + 3) // 4)


def _is_cjk_token_dense_char(char: str) -> bool:
    code = ord(char)
    return (
        0x1100 <= code <= 0x11FF
        or 0x2E80 <= code <= 0x9FFF
        or 0xA960 <= code <= 0xA97F
        or 0xAC00 <= code <= 0xD7AF
        or 0xF900 <= code <= 0xFAFF
        or 0xFF00 <= code <= 0xFFEF
    )


def estimate_image_tokens(
    message: dict,
    cost_per_image: int = DEFAULT_IMAGE_TOKEN_COST,
) -> int:
    """Count image parts in a message and charge a fixed cost per image."""
    if not isinstance(message, dict):
        return 0

    count = 0
    content = message.get("content")
    if isinstance(content, list):
        count += sum(
            1
            for part in content
            if isinstance(part, dict)
            and part.get("type") in {"image", "image_url", "input_image"}
        )

    anthropic_blocks = message.get("_anthropic_content_blocks")
    if isinstance(anthropic_blocks, list):
        count += sum(
            1
            for part in anthropic_blocks
            if isinstance(part, dict) and part.get("type") == "image"
        )

    if isinstance(content, dict) and content.get("_multimodal"):
        inner = content.get("content")
        if isinstance(inner, list):
            count += sum(
                1
                for part in inner
                if isinstance(part, dict)
                and part.get("type") in {"image", "image_url"}
            )
    return count * cost_per_image


def estimate_message_tokens_rough(
    message: dict,
    text_estimator: TextEstimator | None = None,
) -> int:
    """Estimate text tokens for one message; image bytes are stripped first.

    text_estimator defaults to estimate_text_tokens_rough. Hosts may still
    inject a different estimator without importing this module's siblings.
    """
    if text_estimator is None:
        text_estimator = estimate_text_tokens_rough
    if not isinstance(message, dict):
        return text_estimator(str(message))

    shadow: dict[str, Any] = {}
    for key, value in message.items():
        if key == "_anthropic_content_blocks":
            continue
        if key != "content":
            shadow[key] = value
            continue
        if isinstance(value, list):
            cleaned = []
            for part in value:
                if (
                    isinstance(part, dict)
                    and part.get("type") in {"image", "image_url", "input_image"}
                ):
                    cleaned.append(
                        {"type": part.get("type"), "image": "[stripped]"}
                    )
                else:
                    cleaned.append(part)
            shadow[key] = cleaned
        elif isinstance(value, dict) and value.get("_multimodal"):
            shadow[key] = value.get("text_summary", "")
        else:
            shadow[key] = value
    return text_estimator(str(shadow))


def estimate_messages_tokens_rough(
    messages: list[dict],
    text_estimator: TextEstimator | None = None,
    image_estimator: ImageEstimator | None = None,
) -> int:
    """Sum text and image estimates across a message list."""
    if text_estimator is None:
        text_estimator = estimate_text_tokens_rough
    if image_estimator is None:
        image_estimator = estimate_image_tokens
    total = 0
    for message in messages or []:
        total += estimate_message_tokens_rough(message, text_estimator)
        total += image_estimator(message)
    return total


def estimate_tool_tokens_rough(tools: list[dict]) -> int:
    """Estimate tool-schema tokens at about 4 characters per token."""
    total_chars = 0
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function")
        if isinstance(function, dict):
            name = function.get("name") or ""
            description = function.get("description") or ""
            parameters = function.get("parameters") or {}
        else:
            name = tool.get("name") or ""
            description = tool.get("description") or ""
            parameters = tool.get("parameters") or {}

        if isinstance(name, str):
            total_chars += len(name)
        if isinstance(description, str):
            total_chars += len(description)
        try:
            total_chars += len(
                json.dumps(
                    parameters,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        except Exception:
            total_chars += len(str(parameters))

    return (total_chars + 3) // 4
