from capability.model.runtime.assemble import ModelCardCapability
from capability.model.runtime.assemble import register_card

CARD_CONFIG = {
        "provider": "gemini",
        "interface": "gemini",
        "model": "your-gemini-model",
        "api_key_env": "GEMINI_API_KEY",
        "base_url": "",
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
        "card_id": "gemini_model",
        "routes": ["gemini_model", "gemini"],
}

PLUGIN_NAME = "model.card.gemini_model"
PLUGIN_VERSION = "1.0"


class GeminiModelCard(ModelCardCapability):
    name = "model.card.gemini_model"
    version = "1.0"
    kind = "model.card"
    provides = ("model.card", "model.card.gemini_model", "gemini_model", "gemini")
    requires = ("model.interface.gemini",)
    constraints = {"domain": "model"}
    config = CARD_CONFIG


def activate(res, config):
    register_card(res, config or CARD_CONFIG)
