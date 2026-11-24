"""discover_tools reads the list MCPHub is already serving."""

import json

import pytest

import capability.tools.external_tools.mcp.mcp_tool_manager_plugin as plugin


def test_discover_tools_returns_name_description_and_parameters(monkeypatch) -> None:
    monkeypatch.setattr(plugin, "load", lambda kind, body, call_params=None: json.dumps({
        "success": True,
        "tools": [{
            "name": "time-get_current_time",
            "description": "Current time",
            "parameters": {"type": "object", "properties": {"timezone": {"type": "string"}}},
            "extra": True,
        }],
    }))

    assert plugin.discover_tools() == [{
        "name": "time-get_current_time",
        "description": "Current time",
        "parameters": {"type": "object", "properties": {"timezone": {"type": "string"}}},
    }]


def test_discover_tools_rejects_an_empty_list(monkeypatch) -> None:
    monkeypatch.setattr(
        plugin,
        "load",
        lambda kind, body, call_params=None: json.dumps({"success": True, "tools": []}),
    )

    with pytest.raises(RuntimeError, match="MCPHub returned no tools"):
        plugin.discover_tools()


def test_discover_tools_reports_a_down_hub(monkeypatch) -> None:
    def load(kind, body, call_params=None):
        del kind, body, call_params
        raise RuntimeError("MCPHub is not running at http://127.0.0.1:3000/mcp")

    monkeypatch.setattr(plugin, "load", load)

    with pytest.raises(RuntimeError, match="MCPHub is not running at"):
        plugin.discover_tools()
