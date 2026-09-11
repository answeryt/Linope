from kernel.compose.capability.capability import Capability


class RequestShapeParamsCapability(Capability):
    name = "model.parameters.request_shape"
    version = "1.0"
    kind = "model.parameter"
    provides = (
        "model.parameters",
        "model.parameters.stream_options",
        "model.parameters.generate_kwargs",
        "model.parameters.extra_body",
    )


PLUGIN_NAME = "model.parameters.request_shape"
PLUGIN_VERSION = "1.0"


def apply_stream_options(
    request_kwargs: dict,
    stream: bool,
) -> None:
    if stream:
        request_kwargs["stream_options"] = {"include_usage": True}


def apply_generate_kwargs(
    request_kwargs: dict,
    generate_kwargs: dict,
) -> None:
    request_kwargs.update(generate_kwargs)


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

