def apply_tool_choice(
    request_kwargs: dict,
    formatted_tool_choice: str | dict | None,
) -> None:
    if formatted_tool_choice is not None:
        request_kwargs["tool_choice"] = formatted_tool_choice
