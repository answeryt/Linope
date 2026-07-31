def apply_modalities(
    request_kwargs: dict,
    parameters: object,
) -> None:
    voice = getattr(parameters, "voice", None)
    if voice is not None:
        request_kwargs["modalities"] = ["text", "audio"]
