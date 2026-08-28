def apply_reasoning_effort(
    request_kwargs: dict,
    parameters: object,
) -> None:
    thinking_enable = getattr(parameters, "thinking_enable", False)
    reasoning_effort = getattr(parameters, "reasoning_effort", None)
    if thinking_enable and reasoning_effort is not None:
        request_kwargs["reasoning_effort"] = reasoning_effort
