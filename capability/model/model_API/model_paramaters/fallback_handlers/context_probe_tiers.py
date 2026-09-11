from kernel.compose.capability.capability import Capability


class ContextProbeTiersCapability(Capability):
    name = "model.fallback.context_probe_tiers"
    version = "1.0"
    kind = "model.fallback"
    provides = ("model.fallback", "model.fallback.context_probe_tiers")
    requires = ("model.fallback.context_defaults",)


PLUGIN_NAME = "model.fallback.context_probe_tiers"
PLUGIN_VERSION = "1.0"


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


def recover(error, request):
    current = request.get("context_length")
    if not isinstance(current, int):
        return None
    lower = get_next_context_probe_tier(int(current))
    if isinstance(lower, int) and lower >= 1:
        return {**dict(request), "context_length": lower}
    return None
