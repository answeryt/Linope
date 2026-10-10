"""The MCP tool manager can be loaded inside a capability process."""

from __future__ import annotations

import pytest

from capability.tools.external_tools.mcp import mcp_tool_manager_plugin as plugin


def test_listing_tools_and_refusing_another_kind(monkeypatch) -> None:
    monkeypatch.setattr(plugin, "_MANAGER", None)
    assert plugin.load("tool", {"name": "list"}) == {"tools": []}
    with pytest.raises(ValueError, match="不能装入"):
        plugin.load("prompt", "你好")


def test_a_registered_handler_is_called_by_its_prefixed_name(monkeypatch) -> None:
    monkeypatch.setattr(plugin, "_MANAGER", None)
    called: list[dict] = []

    def handler(arguments: dict) -> dict:
        called.append(arguments)
        return arguments

    plugin.manager().register_server_tools(
        "demo",
        [type("Tool", (), {"name": "echo", "description": "", "inputSchema": {}})()],
        handler_factory=lambda _name: handler,
    )
    name = plugin.prefixed_tool_name("demo", "echo")
    assert plugin.load("tool", {"name": name, "arguments": {"text": "hi"}}) == {"text": "hi"}
    assert called == [{"text": "hi"}]
