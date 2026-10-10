# -*- coding: utf-8 -*-
"""Default context windows and recovery from provider limit errors."""

from __future__ import annotations

import re
from typing import Any


DEFAULT_FALLBACK_CONTEXT = 256_000
MINIMUM_CONTEXT_LENGTH = 64_000

CONTEXT_PROBE_TIERS = (
    256_000,
    128_000,
    64_000,
    32_000,
    16_000,
    8_000,
)

CONTEXT_LIMIT_PATTERNS = (
    r"max_model_len\s*(?:is\s*)?[:=(]?\s*(\d{4,})",
    r"maximum model length\s*(?:is\s*)?[:=(]?\s*(\d{4,})",
    r"(?:max(?:imum)?|limit)\s*(?:context\s*)?"
    r"(?:length|size|window)?\s*(?:is|of|:)?\s*(\d{4,})",
    r"context\s*(?:length|size|window)\s*(?:is|of|:)?\s*(\d{4,})",
    r"(\d{4,})\s*(?:token)?\s*(?:context|limit)",
    r">\s*(\d{4,})\s*(?:max|limit|token)",
    r"(\d{4,})\s*(?:max(?:imum)?)\b",
)


DEFAULT_CONTEXT_LENGTHS = {
    "claude-fable-5-1": 1_000_000,
    "claude-fable-5": 1_000_000,
    "claude-fable": 1_000_000,
    "claude-opus-5": 1_000_000,
    "claude-sonnet-5": 1_000_000,
    "claude-opus-4-8": 1_000_000,
    "claude-opus-4.8": 1_000_000,
    "claude-opus-4-7": 1_000_000,
    "claude-opus-4.7": 1_000_000,
    "claude-opus-4-6": 1_000_000,
    "claude-sonnet-4-6": 1_000_000,
    "claude-opus-4.6": 1_000_000,
    "claude-sonnet-4.6": 1_000_000,
    "claude": 200_000,
    "gpt-5.6-luna": 1_050_000,
    "gpt-5.6-terra": 1_050_000,
    "gpt-5.6-sol": 1_050_000,
    "gpt-5.5": 1_050_000,
    "gpt-5.4-nano": 400_000,
    "gpt-5.4-mini": 400_000,
    "gpt-5.4": 1_050_000,
    "gpt-5.3-codex-spark": 128_000,
    "gpt-5.1-chat": 128_000,
    "gpt-5": 400_000,
    "gpt-4.1": 1_047_576,
    "gpt-4": 128_000,
    "gemini": 1_048_576,
    "gemma-4": 256_000,
    "gemma4": 256_000,
    "gemma-4-31b": 256_000,
    "gemma-3": 131_072,
    "gemma": 8_192,
    "deepseek-v4-pro": 1_000_000,
    "deepseek-v4-flash": 1_000_000,
    "deepseek-chat": 1_000_000,
    "deepseek-reasoner": 1_000_000,
    "deepseek": 128_000,
    "llama": 131_072,
    "qwen3.6-plus": 1_048_576,
    "qwen3.7-plus": 1_048_576,
    "qwen3-coder-plus": 1_000_000,
    "qwen3-coder": 262_144,
    "qwen3-max": 262_144,
    "qwen": 131_072,
    "minimax-m3": 1_000_000,
    "minimax": 204_800,
    "glm-5.2": 1_048_576,
    "glm": 202_752,
    "grok-composer": 200_000,
    "grok-build-latest": 500_000,
    "grok-build": 256_000,
    "grok-code-fast": 256_000,
    "grok-2-vision": 8_192,
    "grok-4-fast": 2_000_000,
    "grok-4.20": 2_000_000,
    "grok-4.5": 500_000,
    "grok-4.3": 1_000_000,
    "grok-4": 256_000,
    "grok-3": 131_072,
    "grok-2": 131_072,
    "grok": 131_072,
    "kimi-k3": 1_048_576,
    "kimi": 262_144,
    "solar-open2": 262_144,
    "solar-pro3": 131_072,
    "solar-pro2": 65_536,
    "solar-mini": 32_768,
    "hy3-preview": 262_144,
    "hy3": 262_144,
    "nemotron": 131_072,
    "trinity": 262_144,
    "elephant": 262_144,
    "qwen/qwen3.5-397b-a17b": 131_072,
    "qwen/qwen3.5-35b-a3b": 131_072,
    "deepseek-ai/deepseek-v3.2": 65_536,
    "moonshotai/kimi-k2.5": 262_144,
    "moonshotai/kimi-k2.6": 262_144,
    "moonshotai/kimi-k2-thinking": 262_144,
    "minimaxai/minimax-m2.5": 204_800,
    "xiaomimimo/mimo-v2-flash": 262_144,
    "mimo-v2-pro": 1_048_576,
    "mimo-v2.5-pro": 1_048_576,
    "mimo-v2.5": 1_048_576,
    "mimo-v2-omni": 262_144,
    "mimo-v2-flash": 262_144,
    "zai-org/glm-5": 202_752,
}


def resolve_default_context_length(model: str) -> int:
    """Match model keys by longest substring first; return 256K if no match."""
    model_lower = str(model or "").lower()
    for model_key, context_length in sorted(
        DEFAULT_CONTEXT_LENGTHS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if model_key in model_lower:
            return context_length
    return DEFAULT_FALLBACK_CONTEXT


def recover_missing_context_length(error, request):
    if not isinstance(request.get("context_length"), int):
        default = resolve_default_context_length(str(request.get("model") or "unknown/model"))
        if isinstance(default, int) and default >= 1:
            request["context_length"] = default
    return None


def get_next_context_probe_tier(current_length: int) -> int | None:
    """Return the next lower context probe tier."""
    for context_length in CONTEXT_PROBE_TIERS:
        if context_length < current_length:
            return context_length
    return None


def recover_context_probe_tier(error, request):
    current = request.get("context_length")
    if not isinstance(current, int):
        return None
    lower = get_next_context_probe_tier(int(current))
    if isinstance(lower, int) and lower >= 1:
        return {**dict(request), "context_length": lower}
    return None


def parse_context_limit_from_error(error_message: str) -> int | None:
    """Extract the explicitly reported context window from provider error text."""
    error_lower = str(error_message or "").lower()
    for pattern in CONTEXT_LIMIT_PATTERNS:
        match = re.search(pattern, error_lower)
        if not match:
            continue
        context_limit = int(match.group(1))
        if 1024 <= context_limit <= 10_000_000:
            return context_limit
    return None


def resolve_lower_context_limit_from_error(
    error_message: str,
    current_context_length: int,
) -> int | None:
    """Return a corrected value only when the provider reports a smaller window."""
    parsed_limit = parse_context_limit_from_error(error_message)
    if parsed_limit is not None and parsed_limit < current_context_length:
        return parsed_limit
    return None


def recover_lower_context_from_error(error, request):
    current = request.get("context_length")
    if not isinstance(current, int):
        return None
    lower = resolve_lower_context_limit_from_error(str(error), current)
    if isinstance(lower, int) and lower >= 1:
        return {**dict(request), "context_length": lower}
    return None


def parse_available_output_tokens_from_error(
    error_message: str,
) -> int | None:
    """Extract available output tokens from known provider error formats."""
    error_lower = str(error_message or "").lower()
    if not _looks_like_output_cap_error(error_lower):
        return None

    range_match = re.search(
        r"range of max_tokens should be\s*\[\s*\d+\s*,\s*(\d+)\s*\]",
        error_lower,
    )
    if range_match:
        output_limit = int(range_match.group(1))
        return output_limit if output_limit >= 1 else None

    for pattern in (
        r"available_tokens[:\s]+(\d+)",
        r"available\s+tokens[:\s]+(\d+)",
        r"=\s*(\d+)\s*$",
    ):
        match = re.search(pattern, error_lower)
        if match:
            available = int(match.group(1))
            if available >= 1:
                return available

    context_match = re.search(
        r"maximum context length is (\d+)",
        error_lower,
    )
    parts_match = re.search(
        r"\((\d+)\s+of text input,\s*(\d+)\s+of tool input,"
        r"\s*(\d+)\s+in the output\)",
        error_lower,
    )
    if context_match and parts_match:
        available = (
            int(context_match.group(1))
            - int(parts_match.group(1))
            - int(parts_match.group(2))
        )
        if available >= 1:
            return available

    context_tokens = re.search(
        r"maximum context length is (\d+)\s*token",
        error_lower,
    )
    prompt_characters = re.search(
        r"prompt contains (\d+)\s*character",
        error_lower,
    )
    if context_tokens and prompt_characters:
        estimated_input = (int(prompt_characters.group(1)) + 2) // 3
        available = int(context_tokens.group(1)) - estimated_input
        if available >= 1:
            return available

    prompt_tokens = re.search(
        r"prompt contains (?:at least )?(\d+)\s*input tokens",
        error_lower,
    )
    if context_tokens and prompt_tokens:
        available = int(context_tokens.group(1)) - int(prompt_tokens.group(1))
        if available >= 1:
            return available
    return None


def is_output_cap_error(error_message: str) -> bool:
    """Check if the error is caused by the output token parameter being too large."""
    error_lower = str(error_message or "").lower()
    mentions_output_parameter = any(
        name in error_lower
        for name in (
            "max_tokens",
            "max_output_tokens",
            "max_completion_tokens",
        )
    )
    if not mentions_output_parameter:
        return False

    output_cap_signal = (
        "range of max_tokens should be" in error_lower
        or "available_tokens" in error_lower
        or "available tokens" in error_lower
        or (
            "in the output" in error_lower
            and "maximum context length" in error_lower
        )
        or (
            "requested" in error_lower
            and "output tokens" in error_lower
        )
        or "should be" in error_lower
        or "less than or equal" in error_lower
        or "must be" in error_lower
    )
    if not output_cap_signal:
        return False

    input_overflow_signal = any(
        phrase in error_lower
        for phrase in (
            "input is too long",
            "prompt is too long",
            "prompt too long",
            "input token",
            "prompt length",
            "prompt contains",
            "reduce the length",
        )
    )
    return not input_overflow_signal


def _looks_like_output_cap_error(error_lower: str) -> bool:
    return (
        "max_tokens" in error_lower
        and (
            "available_tokens" in error_lower
            or "available tokens" in error_lower
        )
    ) or (
        "in the output" in error_lower
        and "maximum context length" in error_lower
    ) or (
        "maximum context length" in error_lower
        and "requested" in error_lower
        and "output tokens" in error_lower
    ) or "range of max_tokens should be" in error_lower


def recover_output_token_cap(error, request):
    message = str(error)
    if not is_output_cap_error(message):
        return None
    available = parse_available_output_tokens_from_error(message)
    if isinstance(available, int) and available >= 1:
        return {**dict(request), "max_tokens": available}
    return None


def recover_request(error, request: dict[str, Any]) -> dict[str, Any] | None:
    """Try context fill, then explicit lower window, output cap, then probe tier."""
    recover_missing_context_length(error, request)
    lowered = recover_lower_context_from_error(error, request)
    if lowered is not None:
        return lowered
    output = recover_output_token_cap(error, request)
    if output is not None:
        return output
    return recover_context_probe_tier(error, request)
