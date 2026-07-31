def apply_max_completion_tokens(
    request_kwargs: dict,
    parameters: object,
    interface: str = "openai_chat",
) -> None:
    max_tokens = getattr(parameters, "max_tokens", None)
    if max_tokens is None:
        return

    field_name = {
        "openai_chat": "max_completion_tokens",
        "openai_response": "max_output_tokens",
        "gemini": "max_output_tokens",
    }.get(interface)
    if field_name is not None:
        request_kwargs[field_name] = max_tokens
