import json


def estimate_tool_tokens_rough(tools: list[dict]) -> int:
    """按工具名称、描述和参数 Schema 的字符量粗略估算 Token。

    与原脚本相同，主要字段总字符数按约 4 字符一个 Token 换算。
    本插件不维护跨调用缓存，缓存策略留给未来连接层决定。
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
