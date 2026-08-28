from typing import Any
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