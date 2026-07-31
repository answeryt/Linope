def apply_extra_body(
    request_kwargs: dict,
    extra_body: dict | None,
) -> None:
    if extra_body is None:
        return

    request_kwargs["extra_body"] = {
        **extra_body,
        **request_kwargs.get("extra_body", {}),
    }
