import re

from kernel.compose.capability.capability import Capability


class ContextErrorRecoveryCapability(Capability):
    name = "model.fallback.context_error_recovery"
    version = "1.0"
    kind = "model.fallback"
    provides = ("model.fallback", "model.fallback.context_error_recovery")
    requires = ("model.fallback.context_defaults",)


PLUGIN_NAME = "model.fallback.context_error_recovery"
PLUGIN_VERSION = "1.0"


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
    """Return a corrected value only when the provider explicitly reports a smaller window."""
    parsed_limit = parse_context_limit_from_error(error_message)
    if parsed_limit is not None and parsed_limit < current_context_length:
        return parsed_limit
    return None


def recover(error, request):
    current = request.get("context_length")
    if not isinstance(current, int):
        return None
    lower = resolve_lower_context_limit_from_error(str(error), current)
    if isinstance(lower, int) and lower >= 1:
        return {**dict(request), "context_length": lower}
    return None
