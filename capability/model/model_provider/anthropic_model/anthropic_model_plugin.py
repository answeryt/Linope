# -*- coding: utf-8 -*-
"""Anthropic model provider plugin. Card identity lives in CARD_CONFIG."""

CARD_CONFIG = {
    "provider": "anthropic",
    "interface": "anthropic",
    "model": "claude-opus-5",
    "api_key_env": "ANTHROPIC_API_KEY",
    "base_url": "https://api.anthropic.com",
    "stream": "UNSET",
    "parameters": {
        "max_tokens": 128000,
        "temperature": "UNSET",
        "top_p": "UNSET",
        "tools": "UNSET",
        "tool_choice": "UNSET",
    },
    "client_kwargs": {},
    "generate_kwargs": {},
    "extra_body": {},
    "card_id": "anthropic_model",
    "routes": ["anthropic_model", "anthropic"],
}


def load(kind, body, call_params=None):
    """Load a prompt through this plugin's card id."""
    from capability.model.model_runtime.model_main import load_named_card

    return load_named_card(CARD_CONFIG["card_id"], kind, body, call_params)


async def load_async(kind, body, call_params=None):
    """Load a prompt on the process event loop without nested asyncio.run."""
    from capability.model.model_runtime.model_main import load_named_card_async

    return await load_named_card_async(
        CARD_CONFIG["card_id"],
        kind,
        body,
        call_params,
    )


def capability_profile(capability_id, changes):
    """Expose this plugin's card as a process profile."""
    from capability.model.model_provider.card_profile import declaration_from_card

    return declaration_from_card(capability_id, CARD_CONFIG, changes)
