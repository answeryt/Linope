"""How a tool result meets the context window.

Search-like tools hand back links and do not occupy the window until a link
is followed. Tools that read or change something may occupy a page when their
result is kept. Compression is a system tool: it does not occupy a page of
its own, and it only appears while one of those capabilities is leased.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ToolEffect(StrEnum):
    """What following this tool does to the context window."""

    LINK = "link"
    OCCUPY = "occupy"
    SYSTEM = "system"


_COMPRESSION_CAPABILITIES = (
    "context.sliding_window",
    "context.summary_compression",
    "context.semantic_compression",
)

_SYSTEM = frozenset(
    {
        "sliding_window",
        "summary_compression",
        "semantic_compression",
        *_COMPRESSION_CAPABILITIES,
    }
)

_LINK = frozenset(
    {
        "firecrawl",
        "tavily",
        "exa",
        "parallel",
        "brave_free",
        "searxng",
        "ddgs",
        "grep",
        "glob",
        "terminal_list",
        "terminal_preview",
        "mcp_tool_manager",
        "mcp_protocol",
        "mcp_resilience",
        "mcp_config",
        "mcp_auth_security",
        "mcp_host_manager",
        "mcp_content",
        "mcp_interaction",
    }
)

_OCCUPY = frozenset(
    {
        "read",
        "read_image",
        "write",
        "edit",
        "str_replace_editor",
        "file",
        "bash",
        "bash_persistent",
        "ask_user",
        "terminal",
        "terminal_open",
        "terminal_close",
        "terminal_close_session",
        "terminal_send",
        "terminal_signal",
        "terminal_read",
        "terminal_read_session",
        "terminal_focus",
    }
)

_declared: dict[str, ToolEffect] = {}


def declare_tool(name: str, effect: ToolEffect) -> None:
    """Record how one MCP tool, or any tool not in the built-in table, behaves."""
    if not name:
        raise ValueError("tool name is required")
    _declared[name] = effect


def forget_tool(name: str) -> None:
    """Drop one declared tool so tests can restore the default."""
    _declared.pop(name, None)


def effect_for(name: str) -> ToolEffect:
    """Classify one tool. An undeclared name, including MCP, only returns links."""
    if name in _declared:
        return _declared[name]
    leaf = name.split(".")[-1]
    if name in _SYSTEM or leaf in _SYSTEM:
        return ToolEffect.SYSTEM
    if name in _OCCUPY or leaf in _OCCUPY:
        return ToolEffect.OCCUPY
    if name in _LINK or leaf in _LINK:
        return ToolEffect.LINK
    return ToolEffect.LINK


def summary_text(text: str) -> str:
    """Shrink one page with the existing deterministic summary fallback."""
    from capability.context.context_compression.summary_compression.static_fallback import (
        build_static_fallback,
    )

    return build_static_fallback(
        [{"role": "user", "content": text}],
        redactor=lambda value: str(value),
        content_text=lambda value: value if isinstance(value, str) else "",
        is_real_user=lambda message: message.get("role") == "user",
        normalize_summary=lambda value: str(value).strip(),
        max_chars=240,
        turn_max_chars=240,
    )


def compression_leased(store: Any) -> bool:
    """A compression capability is leased when one of its processes is running."""
    running = getattr(store, "running_processes", None)
    if not callable(running):
        return False
    return any(bool(running(capability_id)) for capability_id in _COMPRESSION_CAPABILITIES)


def leased_tool_names(store: Any) -> tuple[str, ...]:
    """Tool relations for processes that are up. System compressors are separate."""
    live = getattr(store, "live_processes", None)
    if not callable(live):
        return ()
    names: list[str] = []
    for record in live():
        capability_id = str(record.get("capability_id") or "")
        if not capability_id.startswith("tools."):
            continue
        name = capability_id[len("tools.") :]
        if not name or effect_for(name) is ToolEffect.SYSTEM:
            continue
        names.append(name)
    return tuple(sorted(set(names)))
