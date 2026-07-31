"""Anthropic 提示词缓存策略。

单一布局：``system_and_3``。4 个 cache_control 断点——
系统提示词 + 最后 3 条非 system 消息，均使用相同 TTL（5m 或 1h）。
在同一会话的多轮对话中，可将输入 token 成本降低约 75%。

纯函数——无类状态，不依赖 AIAgent。
"""

import copy
from typing import Any, Dict, List


def _apply_cache_marker(msg: dict, cache_marker: dict, native_anthropic: bool = False) -> None:
    """Add cache_control to a single message, handling all format variations."""
    role = msg.get("role", "")
    content = msg.get("content")

    if role == "tool" and native_anthropic:
        # Native Anthropic layout: top-level marker; the adapter moves it
        # inside the tool_result block.
        msg["cache_control"] = cache_marker
        return

    if content is None or content == "":
        if role == "tool" and not native_anthropic:
            # OpenRouter rejects top-level cache_control on role:tool (silent
            # hang) and an empty message has no content part to carry the
            # marker — skip. Non-empty tool content falls through below and
            # gets the marker on a content part, which OpenRouter honors.
            return
        if role == "assistant" and not native_anthropic:
            # Empty assistant turns are pure tool_calls. A top-level marker
            # here is ignored on the envelope layout, so skip.
            return
        msg["cache_control"] = cache_marker
        return

    if isinstance(content, str):
        msg["content"] = [
            {"type": "text", "text": content, "cache_control": cache_marker}
        ]
        return

    if isinstance(content, list) and content:
        last = content[-1]
        if isinstance(last, dict):
            last["cache_control"] = cache_marker


def _can_carry_marker(msg: dict, native_anthropic: bool) -> bool:
    """若在此消息上放置 marker，提供方是否真的会生效。

    在原生 Anthropic 布局下，每条消息都有效（顶层 marker 由适配器
    重新定位）。在 envelope 布局（OpenRouter 等）下，仅 content 部分
    内的 marker 会被识别：空内容消息（例如纯 tool_calls 的 assistant
    轮次）和空 tool 消息若加上顶层 marker，提供方会忽略——从而浪费
    四个断点之一。跳过这些情况，让断点落在真正有效的消息上。
    """
    if native_anthropic:
        return True
    content = msg.get("content")
    if content is None or content == "":
        return False
    if isinstance(content, list):
        # _apply_cache_marker only marks the LAST content part, so the carrier
        # predicate must agree: a list whose last element isn't a dict cannot
        # actually receive a marker and would waste a breakpoint. Mirror the
        # `content` truthiness + last-element-dict check in _apply_cache_marker.
        return bool(content) and isinstance(content[-1], dict)
    return isinstance(content, str)


def _build_marker(ttl: str) -> Dict[str, str]:
    """Build a cache_control marker dict for the given TTL ('5m' or '1h')."""
    marker: Dict[str, str] = {"type": "ephemeral"}
    if ttl == "1h":
        marker["ttl"] = "1h"
    return marker


def apply_anthropic_cache_control(
    api_messages: List[Dict[str, Any]],
    cache_ttl: str = "5m",
    native_anthropic: bool = False,
) -> List[Dict[str, Any]]:
    """为 Anthropic 模型对消息应用 system_and_3 缓存策略。

    最多放置 4 个 cache_control 断点：系统提示词 + 最后 3 条非 system
    消息，均使用相同 TTL。

    Returns:
        注入 cache_control 断点后的消息深拷贝。
    """
    messages = copy.deepcopy(api_messages)
    if not messages:
        return messages

    marker = _build_marker(cache_ttl)

    breakpoints_used = 0

    if messages[0].get("role") == "system":
        _apply_cache_marker(messages[0], marker, native_anthropic=native_anthropic)
        breakpoints_used += 1

    remaining = 4 - breakpoints_used
    non_sys = [
        i
        for i in range(len(messages))
        if messages[i].get("role") != "system"
        and _can_carry_marker(messages[i], native_anthropic=native_anthropic)
    ]
    for idx in non_sys[-remaining:]:
        _apply_cache_marker(messages[idx], marker, native_anthropic=native_anthropic)

    return messages
