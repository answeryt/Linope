def apply_stream_options(
    request_kwargs: dict,
    stream: bool,
) -> None:
    if stream:
        request_kwargs["stream_options"] = {"include_usage": True}
