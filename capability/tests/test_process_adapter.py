"""Resource parameters stay with the resource kind that declared them."""

from __future__ import annotations

import asyncio
import json
import types

from kernel.resource.definition import ResourceGrant, ResourceKind

from capability.process_adapter import ProcessAdapter
from capability.tools.agent_tools.file_tools import glob_plugin, grep_plugin, read_plugin
from capability.tools.agent_tools.shell_tools import pwsh_plugin


def test_a_tool_call_does_not_receive_sandbox_or_network_parameters() -> None:
    seen: list[tuple[str, str, dict]] = []

    def load(kind, body, call_params=None):
        seen.append(("sync", kind, dict(call_params or {})))
        return body

    adapter = ProcessAdapter([types.SimpleNamespace(load=load)])
    adapter.initialize(_context())

    assert adapter.handle({"operation": "load", "kind": "tool", "body": {"file_path": "README.md"}}) == {
        "file_path": "README.md"
    }
    assert seen == [("sync", "tool", {"workspace": "C:/project"})]
    assert "scope" not in seen[0][2]
    assert "mode" not in seen[0][2]


def test_an_async_tool_call_uses_the_same_parameter_boundary() -> None:
    seen: list[tuple[str, str, dict]] = []

    def load(kind, body, call_params=None):
        raise AssertionError("the async loader should handle this request")

    async def load_async(kind, body, call_params=None):
        seen.append(("async", kind, dict(call_params or {})))
        return "entered"

    adapter = ProcessAdapter([types.SimpleNamespace(load=load, load_async=load_async)])
    adapter.initialize(_context())

    assert asyncio.run(
        adapter.handle_async({"operation": "load", "kind": "tool", "body": {"pattern": "*.md"}})
    ) == "entered"
    assert seen == [("async", "tool", {"workspace": "C:/project"})]


def test_a_non_tool_keeps_settings_and_only_its_own_resource_parameters() -> None:
    seen: list[tuple[str, dict]] = []

    def load(kind, body, call_params=None):
        seen.append((kind, dict(call_params or {})))
        return "ok"

    adapter = ProcessAdapter([types.SimpleNamespace(load=load)])
    adapter.initialize(_context())

    adapter.handle({"operation": "load", "kind": "sandbox", "body": {}})
    adapter.handle({"operation": "load", "kind": "network", "body": {}})

    assert seen[0] == (
        "sandbox",
        {
            "model": "demo-model",
            "mode": "read-only",
            "scope": "host",
            "future_sandbox_flag": "kept-with-sandbox",
        },
    )
    assert seen[1] == ("network", {"model": "demo-model", "channel": "ledger"})


def test_real_file_and_shell_plugins_accept_a_host_scoped_sandbox_grant() -> None:
    context = _context(tool_params={})
    cases = (
        (read_plugin, {"file_path": ".env"}, "blocked"),
        (glob_plugin, {"pattern": "  "}, "invalid pattern"),
        (grep_plugin, {"pattern": "  "}, "invalid pattern"),
        (pwsh_plugin, {"command": "", "description": "list the project"}, "invalid command"),
    )
    for plugin, body, marker in cases:
        adapter = ProcessAdapter([plugin])
        adapter.initialize(context)
        result = adapter.handle({"operation": "load", "kind": "tool", "body": body})
        assert isinstance(result, str)
        assert "unexpected keyword argument" not in result
        payload = json.loads(result)
        assert payload["success"] is False
        assert marker in payload["error"]


def _context(tool_params: dict | None = None):
    return types.SimpleNamespace(
        settings={"id": "card-id", "provider": "local", "model": "demo-model"},
        grants=(
            ResourceGrant(
                resource_id="tool-1",
                kind=ResourceKind.TOOL,
                handle="tool",
                call_params={"workspace": "C:/project"} if tool_params is None else tool_params,
            ),
            ResourceGrant(
                resource_id="sandbox-1",
                kind=ResourceKind.SANDBOX,
                handle="sandbox",
                call_params={
                    "mode": "read-only",
                    "scope": "host",
                    "future_sandbox_flag": "kept-with-sandbox",
                },
            ),
            ResourceGrant(
                resource_id="network-1",
                kind=ResourceKind.NETWORK,
                handle="network",
                call_params={"channel": "ledger"},
            ),
        ),
    )
