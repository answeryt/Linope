CONTEXT_PROBE_TIERS = (
    256_000,
    128_000,
    64_000,
    32_000,
    16_000,
    8_000,
)


def get_next_context_probe_tier(current_length: int) -> int | None:
    """Return the next lower context probe tier."""
    for context_length in CONTEXT_PROBE_TIERS:
        if context_length < current_length:
            return context_length
    return None
