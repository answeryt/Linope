import re

from kernel.compose.capability.capability import Capability


class OutputTokenRecoveryCapability(Capability):
    name = "model.fallback.output_token_recovery"
    version = "1.0"
    kind = "model.fallback"
    provides = ("model.fallback", "model.fallback.output_token_recovery")


PLUGIN_NAME = "model.fallback.output_token_recovery"
PLUGIN_VERSION = "1.0"


def parse_available_output_tokens_from_error(
    error_message: str,
) -> int | None:
    """Extract available output tokens from known provider error formats.

    Only handles output limit exceeded, does not change the model's context window.
    """
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


def recover(error, request):
    message = str(error)
    if not is_output_cap_error(message):
        return None
    available = parse_available_output_tokens_from_error(message)
    if isinstance(available, int) and available >= 1:
        return {**dict(request), "max_tokens": available}
    return None
