from typing import Any
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