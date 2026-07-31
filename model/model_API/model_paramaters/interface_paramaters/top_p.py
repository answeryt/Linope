def apply_top_p(
    request_kwargs: dict,
    parameters: object,
) -> None:
    top_p = getattr(parameters, "top_p", None)
    if top_p is not None:
        request_kwargs["top_p"] = top_p
