"""Budget for one model request. History is not included unless this read names it."""

from __future__ import annotations

from kernel.resource.memory.records import PromptFootprint
from kernel.resource.memory.token_meter import estimate_tokens


def reserves(limit: int) -> tuple[int, int]:
    """Output reserve and safety margin derived from the model context limit."""

    if limit <= 0:
        return 0, 0
    return max(1, limit // 8), max(1, limit // 50)


def footprint(
    *,
    context_limit: int,
    system: str = "",
    message: str = "",
    action: str = "",
    read: str = "",
) -> PromptFootprint:
    output, safety = reserves(context_limit)
    return PromptFootprint(
        context_limit=context_limit,
        system_tokens=estimate_tokens(system),
        message_tokens=estimate_tokens(message),
        action_tokens=estimate_tokens(action),
        read_tokens=estimate_tokens(read),
        output_reserve=output,
        safety_margin=safety,
    )


def context_limit_for(limit: int = 0) -> int:
    """Use a declared limit, or the kernel fallback when none was declared."""

    from kernel.calculate.measure import FALLBACK_CONTEXT_LIMIT

    if isinstance(limit, int) and not isinstance(limit, bool) and limit > 0:
        return limit
    return FALLBACK_CONTEXT_LIMIT
