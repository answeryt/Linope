import re


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
    """从 Provider 错误文本中提取明确报告的上下文窗口。"""
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
    """仅在 Provider 明确报告了更小窗口时返回修正值。"""
    parsed_limit = parse_context_limit_from_error(error_message)
    if parsed_limit is not None and parsed_limit < current_context_length:
        return parsed_limit
    return None
