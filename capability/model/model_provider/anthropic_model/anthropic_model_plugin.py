from capability.model.runtime.assemble import ModelCardCapability
from capability.model.runtime.assemble import register_card

CARD_CONFIG = {
        "provider": "anthropic",
        "interface": "anthropic",
        "model": "your-anthropic-model",
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url": "https://api.anthropic.com",
        "stream": "UNSET",
        "parameters": {
            "max_tokens": "UNSET",
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

PLUGIN_NAME = "model.card.anthropic_model"
PLUGIN_VERSION = "1.0"


class AnthropicModelCard(ModelCardCapability):
    name = "model.card.anthropic_model"
    version = "1.0"
    kind = "model.card"
    provides = ("model.card", "model.card.anthropic_model", "anthropic_model", "anthropic")
    requires = ("model.interface.anthropic",)
    constraints = {"domain": "model"}
    config = CARD_CONFIG


def activate(res, config):
    register_card(res, config or CARD_CONFIG)
