"""Provider usage numbers, normalized to input and output tokens."""

from __future__ import annotations

from typing import Any


_INPUT = (
    "input",
    "input_tokens",
    "prompt_tokens",
    "prompt_token_count",
    "promptTokenCount",
)
_OUTPUT = (
    "output",
    "output_tokens",
    "completion_tokens",
    "candidates_token_count",
    "candidatesTokenCount",
)


def read_usage(raw: object) -> dict[str, int] | None:
    """Copy the counts a provider actually sent. Missing fields stay missing."""
    if raw is None:
        return None
    found: dict[str, int] = {}
    incoming = _pick(raw, _INPUT)
    outgoing = _pick(raw, _OUTPUT)
    if incoming is not None:
        found["input"] = incoming
    if outgoing is not None:
        found["output"] = outgoing
    return found or None


def _pick(raw: object, names: tuple[str, ...]) -> int | None:
    for name in names:
        if isinstance(raw, dict):
            value = raw.get(name)
        else:
            value = getattr(raw, name, None)
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        return value
    return None


def usage_part(usage: dict[str, int] | None) -> dict[str, Any] | None:
    """A stream part the assembler already knows how to merge."""
    if not usage:
        return None
    return {"type": "usage", "usage": dict(usage)}
