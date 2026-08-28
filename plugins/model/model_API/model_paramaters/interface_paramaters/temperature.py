def apply_temperature(
    request_kwargs: dict,
    parameters: object,
) -> None:
    temperature = getattr(parameters, "temperature", None)
    if temperature is not None:
        request_kwargs["temperature"] = temperature
