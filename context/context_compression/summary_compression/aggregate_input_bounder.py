"""Bound aggregate summarizer input while retaining both temporal edges."""


def bound_summary_input(
    content: str,
    *,
    max_chars: int = 160_000,
    head_ratio: float = 0.45,
) -> str:
    if max_chars < 0:
        raise ValueError("max_chars must be non-negative")
    if not 0 <= head_ratio <= 1:
        raise ValueError("head_ratio must be between 0 and 1")
    if len(content) <= max_chars:
        return content

    template = (
        "\n\n...[summary input truncated: omitted {omitted:,} chars from the "
        "middle to keep compression prompt bounded]...\n\n"
    )
    marker = template.format(omitted=len(content))
    if len(marker) >= max_chars:
        return marker[:max_chars]
    for _ in range(2):
        remaining = max(max_chars - len(marker), 0)
        head_chars = int(remaining * head_ratio)
        tail_chars = remaining - head_chars
        omitted = max(len(content) - head_chars - tail_chars, 0)
        marker = template.format(omitted=omitted)
        if len(marker) >= max_chars:
            return marker[:max_chars]
    remaining = max(max_chars - len(marker), 0)
    head_chars = int(remaining * head_ratio)
    tail_chars = remaining - head_chars
    tail = content[-tail_chars:].lstrip() if tail_chars else ""
    return content[:head_chars].rstrip() + marker + tail
