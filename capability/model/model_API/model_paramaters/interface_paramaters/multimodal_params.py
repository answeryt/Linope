from kernel.compose.capability.capability import Capability


class MultimodalParamsCapability(Capability):
    name = "model.parameters.multimodal"
    version = "1.0"
    kind = "model.parameter"
    provides = (
        "model.parameters",
        "model.parameters.modalities",
        "model.parameters.audio",
    )


PLUGIN_NAME = "model.parameters.multimodal"
PLUGIN_VERSION = "1.0"


def apply_modalities(
    request_kwargs: dict,
    parameters: object,
) -> None:
    voice = getattr(parameters, "voice", None)
    if voice is not None:
        request_kwargs["modalities"] = ["text", "audio"]


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

