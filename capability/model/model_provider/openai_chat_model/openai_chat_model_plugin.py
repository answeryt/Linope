from capability.model.runtime.assemble import ModelCardCapability
from capability.model.runtime.assemble import register_card

CARD_CONFIG = {
        "provider": "openai",
        "interface": "openai_chat",
        "model": "gpt-5.6-sol",
        "api_key_env": "OPENAI_API_KEY",
        "organization_env": "OPENAI_ORGANIZATION",
        "base_url": "https://eapi.site/v1",
        "stream": True,
        "parameters": {
            "max_tokens": "UNSET",
            "temperature": "UNSET",
            "top_p": "UNSET",
            "thinking_enable": "UNSET",
            "reasoning_effort": "UNSET",
            "parallel_tool_calls": "UNSET",
            "tools": "UNSET",
            "tool_choice": "UNSET",
        },
        "client_kwargs": {},
        "generate_kwargs": {},
        "extra_body": {},
        "card_id": "openai_chat_model",
        "routes": ["openai_chat_model", "openai"],
}

PLUGIN_NAME = "model.card.openai_chat_model"
PLUGIN_VERSION = "1.0"


class OpenAIChatModelCard(ModelCardCapability):
    name = "model.card.openai_chat_model"
    version = "1.0"
    kind = "model.card"
    provides = ("model.card", "model.card.openai_chat_model", "openai_chat_model", "openai")
    requires = ("model.interface.openai_chat",)
    constraints = {"domain": "model"}
    config = CARD_CONFIG


def activate(res, config):
    register_card(res, config or CARD_CONFIG)
