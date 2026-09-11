from kernel.compose.capability.capability import Capability


class ToolsSelectionParamsCapability(Capability):
    name = "model.parameters.tools"
    version = "1.0"
    kind = "model.parameter"
    provides = (
        "model.parameters",
        "model.parameters.tools",
        "model.parameters.tool_choice",
        "model.parameters.parallel_tool_calls",
    )


PLUGIN_NAME = "model.parameters.tools"
PLUGIN_VERSION = "1.0"


def apply_parallel_tool_calls(
    request_kwargs: dict,
    parameters: object,
) -> None:
    parallel_tool_calls = getattr(parameters, "parallel_tool_calls", True)
    if not parallel_tool_calls:
        request_kwargs["parallel_tool_calls"] = False


def apply_tools(
    request_kwargs: dict,
    formatted_tools: list[dict] | None,
) -> None:
    if formatted_tools is not None:
        request_kwargs["tools"] = formatted_tools


def apply_tool_choice(
    request_kwargs: dict,
    formatted_tool_choice: str | dict | None,
) -> None:
    if formatted_tool_choice is not None:
        request_kwargs["tool_choice"] = formatted_tool_choice

