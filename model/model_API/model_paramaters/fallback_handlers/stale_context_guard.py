def should_reject_cached_context(model: str, context_length: int) -> bool:
    """Identify known stale context caches that report a lower context window."""
    model_lower = str(model or "").lower()
    if _looks_like_kimi(model_lower) and context_length <= 32_768:
        return True
    if "minimax-m3" in model_lower and context_length <= 204_800:
        return True
    if "grok-4.3" in model_lower and context_length <= 256_000:
        return True
    return False


def should_reject_metadata_context(
    model: str,
    context_length: int,
) -> bool:
    """Identify known stale context provider metadata that reports a lower context window."""
    model_lower = str(model or "").lower()
    return _looks_like_kimi(model_lower) and context_length == 32_768


def _looks_like_kimi(model_lower: str) -> bool:
    return model_lower.startswith("kimi") or "moonshot" in model_lower
