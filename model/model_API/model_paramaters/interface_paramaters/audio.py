def apply_audio(
    request_kwargs: dict,
    parameters: object,
) -> None:
    voice = getattr(parameters, "voice", None)
    if voice is not None:
        request_kwargs["audio"] = {
            "voice": voice,
            "format": "pcm16",
        }
