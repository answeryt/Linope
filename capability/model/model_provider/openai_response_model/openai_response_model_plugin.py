from capability.model.runtime.assemble import ModelCardCapability
from capability.model.runtime.assemble import register_card

CARD_CONFIG = {
        "provider": "openai",
        "interface": "openai_response",
        "model": "your-openai-response-model",
        "api_key_env": "OPENAI_API_KEY",
        "organization_env": "OPENAI_ORGANIZATION",
        "base_url": "https://api.openai.com/v1",
        "stream": "UNSET",
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
        "card_id": "openai_response_model",
        "routes": ["openai_response_model"],
}

PLUGIN_NAME = "model.card.openai_response_model"
PLUGIN_VERSION = "1.0"


class OpenAIResponseModelCard(ModelCardCapability):
    name = "model.card.openai_response_model"
    version = "1.0"
    kind = "model.card"
    provides = ("model.card", "model.card.openai_response_model", "openai_response_model")
    requires = ("model.interface.openai_response",)
    constraints = {"domain": "model"}
    config = CARD_CONFIG


def activate(res, config):
    register_card(res, config or CARD_CONFIG)
