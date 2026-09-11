from kernel.compose.capability.capability import Capability


class ContextDefaultsCapability(Capability):
    name = "model.fallback.context_defaults"
    version = "1.0"
    kind = "model.fallback"
    provides = ("model.fallback", "model.fallback.context_defaults")


PLUGIN_NAME = "model.fallback.context_defaults"
PLUGIN_VERSION = "1.0"


DEFAULT_FALLBACK_CONTEXT = 256_000
MINIMUM_CONTEXT_LENGTH = 64_000


DEFAULT_CONTEXT_LENGTHS = {
    "claude-fable-5": 1_000_000,
    "claude-fable": 1_000_000,
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


def recover(error, request):
    if not isinstance(request.get("context_length"), int):
        default = resolve_default_context_length(str(request.get("model") or "unknown/model"))
        if isinstance(default, int) and default >= 1:
            request["context_length"] = default
    return None
