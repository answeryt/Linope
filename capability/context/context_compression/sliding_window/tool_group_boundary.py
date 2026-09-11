"""Tool-call/result boundary alignment primitives."""

from typing import Any


Message = dict[str, Any]


def align_boundary_forward(messages: list[Message], index: int) -> int:
    """Push a compress-start boundary past orphan tool results.

    If ``messages[index]`` is a tool result, slide forward until a non-tool
    message so the summarized region never starts mid-group.
    """
    while index < len(messages) and messages[index].get("role") == "tool":
        index += 1
    return index


def align_boundary_backward(messages: list[Message], index: int) -> int:
    """Pull a compress-end boundary backward around a complete tool group.

    If the boundary follows consecutive tool results, walk back to their parent
    assistant. When that assistant owns ``tool_calls``, place the boundary
    before it. This prevents later orphan sanitization from silently deleting
    results left in the protected tail.
    """
    if index <= 0 or index >= len(messages):
        return index

    check = index - 1
    while check >= 0 and messages[check].get("role") == "tool":
        check -= 1

    if (
        check >= 0
        and messages[check].get("role") == "assistant"
        and messages[check].get("tool_calls")
    ):
        return check
    return index
