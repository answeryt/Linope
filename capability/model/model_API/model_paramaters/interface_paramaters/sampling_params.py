from kernel.compose.capability.capability import Capability


class SamplingParamsCapability(Capability):
    name = "model.parameters.sampling"
    version = "1.0"
    kind = "model.parameter"
    provides = (
        "model.parameters",
        "model.parameters.temperature",
        "model.parameters.top_p",
        "model.parameters.max_tokens",
    )


PLUGIN_NAME = "model.parameters.sampling"
PLUGIN_VERSION = "1.0"


def apply_temperature(
    request_kwargs: dict,
    parameters: object,
) -> None:
    temperature = getattr(parameters, "temperature", None)
    if temperature is not None:
        request_kwargs["temperature"] = temperature


def apply_top_p(
    request_kwargs: dict,
    parameters: object,
) -> None:
    top_p = getattr(parameters, "top_p", None)
    if top_p is not None:
        request_kwargs["top_p"] = top_p


def apply_max_completion_tokens(
    request_kwargs: dict,
    parameters: object,
    interface: str = "openai_chat",
) -> None:
    max_tokens = getattr(parameters, "max_tokens", None)
    if max_tokens is None:
        return

    field_name = {
        "openai_chat": "max_completion_tokens",
        "openai_response": "max_output_tokens",
        "gemini": "max_output_tokens",
    }.get(interface)
    if field_name is not None:
        request_kwargs[field_name] = max_tokens

