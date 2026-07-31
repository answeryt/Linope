def apply_tools(
    request_kwargs: dict,
    formatted_tools: list[dict] | None,
) -> None:
    if formatted_tools is not None:
        request_kwargs["tools"] = formatted_tools
