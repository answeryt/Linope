from typing import Any

from kernel.compose.capability.capability import Capability


class OpenAIResponseInterface(Capability):
    name = "model.interface.openai_response"
    version = "1.0"
    kind = "model.interface"
    provides = ("model.interface", "model.interface.openai_response")
    constraints = {"protocol": "responses"}


PLUGIN_NAME = "model.interface.openai_response"
PLUGIN_VERSION = "1.0"


async def call_api(
    api_key: str,
    organization: str | None,
    base_url: str | None,
    model: str,
    input_items: list[dict[str, Any]],
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
    return await client.responses.create(
        model=model,
        input=input_items,
        stream=stream,
        **request_kwargs,
    )