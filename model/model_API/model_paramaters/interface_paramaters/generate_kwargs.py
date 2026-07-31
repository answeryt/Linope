def apply_generate_kwargs(
    request_kwargs: dict,
    generate_kwargs: dict,
) -> None:
    request_kwargs.update(generate_kwargs)
