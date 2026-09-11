from typing import Any

from kernel.compose.capability.capability import Capability


class OpenAIChatInterface(Capability):
    name = "model.interface.openai_chat"
    version = "1.0"
    kind = "model.interface"
    provides = ("model.interface", "model.interface.openai_chat")
    constraints = {"protocol": "chat"}


PLUGIN_NAME = "model.interface.openai_chat"
PLUGIN_VERSION = "1.0"


async def call_api(
    api_key: str,
    organization: str | None,
    base_url: str | None,
    model: str,
    messages: list[dict[str, Any]],
    stream: bool,
    client_kwargs: dict[str, Any],
    request_kwargs: dict[str, Any],
) -> Any:
    import openai
    client = openai.AsyncClient(
        api_key=api_key,
        organization=organization,
        base_url=base_url,
        **client_kwargs,
    )
    return await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=stream,
        **request_kwargs,
    )