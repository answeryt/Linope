from typing import Any

from kernel.compose.capability.capability import Capability


class GeminiInterface(Capability):
    name = "model.interface.gemini"
    version = "1.0"
    kind = "model.interface"
    provides = ("model.interface", "model.interface.gemini")
    constraints = {"protocol": "contents"}


PLUGIN_NAME = "model.interface.gemini"
PLUGIN_VERSION = "1.0"


async def call_api(
    api_key: str,
    model: str,
    contents: list[Any],
    config: dict[str, Any],
    stream: bool,
    client_kwargs: dict[str, Any],
) -> Any:
    from google import genai
    client = genai.Client(
        api_key=api_key,
        **client_kwargs,
    )
    if stream:
        return await client.aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        )
    return await client.aio.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )