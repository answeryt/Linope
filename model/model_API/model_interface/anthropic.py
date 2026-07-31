from typing import Any
async def call_api(
    api_key: str,
    base_url: str | None,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    stream: bool,
    client_kwargs: dict[str, Any],
    request_kwargs: dict[str, Any],
) -> Any:
    import anthropic


    client = anthropic.AsyncAnthropic(
        api_key=api_key,
        base_url=base_url,
        **client_kwargs,
    )
    return await client.messages.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        stream=stream,
        **request_kwargs,
    )