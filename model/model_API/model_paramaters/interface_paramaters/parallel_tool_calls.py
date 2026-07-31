def apply_parallel_tool_calls(
    request_kwargs: dict,
    parameters: object,
) -> None:
    parallel_tool_calls = getattr(parameters, "parallel_tool_calls", True)
    if not parallel_tool_calls:
        request_kwargs["parallel_tool_calls"] = False
