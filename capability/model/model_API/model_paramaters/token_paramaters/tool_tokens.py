import json

from kernel.compose.capability.capability import Capability


class ToolTokensCapability(Capability):
    name = "model.tokens.tool"
    version = "1.0"
    kind = "model.token"
    provides = ("model.tokens.tool",)


PLUGIN_NAME = "model.tokens.tool"
PLUGIN_VERSION = "1.0"


def estimate_tool_tokens_rough(tools: list[dict]) -> int:
    """Estimate the token count for a list of tools, using a rough approximation based on the character count of the tool name, description, and parameter schema.

    The total character count of the main fields is approximately 4 characters per token.
    This plugin does not maintain cross-call caching, the caching strategy is left to the future connection layer.
    """
    total_chars = 0
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function")
        if isinstance(function, dict):
            name = function.get("name") or ""
            description = function.get("description") or ""
            parameters = function.get("parameters") or {}
        else:
            name = tool.get("name") or ""
            description = tool.get("description") or ""
            parameters = tool.get("parameters") or {}

        if isinstance(name, str):
            total_chars += len(name)
        if isinstance(description, str):
            total_chars += len(description)
        try:
            total_chars += len(
                json.dumps(
                    parameters,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        except Exception:
            total_chars += len(str(parameters))

    return (total_chars + 3) // 4
