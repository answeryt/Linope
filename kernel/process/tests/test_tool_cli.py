"""Run agent tools through the real linope command line.

``linope.cmd`` changes to the repository before it starts Python, so these
calls use ``python -m kernel.command``, the entry that script runs, with the
temporary directory as the working directory.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOKEN = "LINOPE_TOOL_OK"
NOTE = "note.txt"
HOST = "Host must inject"

# Plugins that define load() and can finish without a host or network.
_READY = frozenset(
    {
        "tools.write",
        "tools.edit",
        "tools.read",
        "tools.glob",
        "tools.grep",
        "tools.read_image",
        "tools.str_replace_editor",
        "tools.bash",
        "tools.bash_persistent",
    }
)

# MCP registry. Listing does not open a network connection.
_MCP = frozenset({"tools.mcp_tool_manager"})

# Plugins that define load() but need a host, or a connection that fails here.
_EXPLAINED = frozenset(
    {
        "tools.terminal_open",
        "tools.terminal_send",
        "tools.terminal_read_session",
        "tools.terminal_list",
        "tools.terminal_signal",
        "tools.terminal_close_session",
        "tools.ask_user",
    }
)

# Search backends. Keyed ones fail closed without a secret. ddgs needs its package.
_SEARCH = frozenset(
    {
        "tools.firecrawl",
        "tools.tavily",
        "tools.exa",
        "tools.parallel",
        "tools.brave_free",
        "tools.searxng",
        "tools.ddgs",
    }
)

_SEARCH_KEYS = {
    "tools.firecrawl": "FIRECRAWL_API_KEY",
    "tools.tavily": "TAVILY_API_KEY",
    "tools.exa": "EXA_API_KEY",
    "tools.parallel": "PARALLEL_API_KEY",
    "tools.brave_free": "BRAVE_SEARCH_API_KEY",
    "tools.searxng": "SEARXNG_URL",
}

# Present as files, but discovery skips them because they have no load().
_UNREGISTERED = frozenset(
    {
        "tools.file",
        "tools.terminal",
        "tools.terminal_close",
        "tools.terminal_focus",
        "tools.terminal_preview",
        "tools.terminal_read",
    }
)


def _invoke(
    tmp_path: Path,
    capability: str,
    body: dict,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    store = tmp_path / "resources.json"
    run_env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUTF8": "1"}
    if env is not None:
        run_env = env
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "kernel.command",
            "capability",
            "load",
            capability,
            "tool",
            json.dumps(body, ensure_ascii=False),
            "--resource-store",
            str(store),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=180,
        env=run_env,
    )


def _tool_result(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stderr or result.stdout
    payload = ast.literal_eval(result.stdout.strip())
    assert payload["event"] == "result", payload
    raw = payload["result"]
    if isinstance(raw, str):
        parsed = json.loads(raw)
    else:
        parsed = raw
    assert isinstance(parsed, dict), parsed
    return parsed


def _load(tmp_path: Path, capability: str, body: dict) -> dict:
    parsed = _tool_result(_invoke(tmp_path, capability, body))
    assert parsed["success"] is True, parsed
    return parsed


def _needs_host(tmp_path: Path, capability: str, body: dict) -> dict:
    parsed = _tool_result(_invoke(tmp_path, capability, body))
    assert parsed["success"] is False, parsed
    assert HOST in str(parsed.get("error")), parsed
    return parsed


def _unknown(tmp_path: Path, capability: str) -> None:
    result = _invoke(tmp_path, capability, {})
    assert result.returncode != 0, result.stdout
    assert f"Unknown capability instance {capability!r}" in result.stderr


def _bash(tmp_path: Path, capability: str) -> str:
    parsed = _tool_result(
        _invoke(
            tmp_path,
            capability,
            {"command": f"echo {TOKEN}", "description": "print a marker"},
        )
    )
    if parsed.get("success") is not True:
        assert parsed.get("error") == "bash is not available on this host", parsed
        return "no-bash"
    if parsed.get("exitCode") == 0 and TOKEN in str(parsed.get("text")):
        return "ok"
    # The process answered. A broken host bash still has to report the exit.
    assert parsed.get("exitCode") not in (None, 0), parsed
    assert str(parsed.get("text") or ""), parsed
    return f"exit-{parsed['exitCode']}"


def _discovered_tools() -> set[str]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from kernel.process.process_creat.instances import discover_instances

    return {name for name in discover_instances() if name.startswith("tools.")}


def _check_catalog() -> None:
    found = _discovered_tools()
    expected = _READY | _EXPLAINED | _MCP | _SEARCH
    missing = sorted(expected - found)
    extra = sorted(found - expected)
    assert not missing and not extra, f"missing={missing} extra={extra}"
    assert _UNREGISTERED.isdisjoint(found)


def test_linope_load_runs_file_tools(tmp_path: Path) -> None:
    written = _load(
        tmp_path,
        "tools.write",
        {"file_path": NOTE, "content": f"before {TOKEN}\n"},
    )
    note = tmp_path / NOTE
    assert note.is_file()
    assert TOKEN in note.read_text(encoding="utf-8")
    assert Path(written["path"]) == note.resolve()

    edited = _load(
        tmp_path,
        "tools.edit",
        {
            "file_path": NOTE,
            "old_string": f"before {TOKEN}",
            "new_string": f"after {TOKEN}",
        },
    )
    assert edited["replacements"] == 1
    assert note.read_text(encoding="utf-8") == f"after {TOKEN}\n"

    read = _load(tmp_path, "tools.read", {"file_path": NOTE})
    assert TOKEN in read["content"]
    assert read["lineCount"] == 1

    found = _load(tmp_path, "tools.glob", {"pattern": NOTE, "path": "."})
    assert NOTE in found["files"]

    matched = _load(tmp_path, "tools.grep", {"pattern": TOKEN, "path": NOTE})
    assert matched["count"] >= 1
    assert any(
        TOKEN in item["text"]
        for items in matched["matches"].values()
        for item in items
    )


def test_linope_load_runs_every_agent_tool(tmp_path: Path) -> None:
    lines = run_every_tool(tmp_path)
    assert lines[-1] == "ok"
    assert sum(1 for line in lines if line.startswith("tools.")) == (
        len(_READY) + len(_EXPLAINED) + len(_MCP) + len(_UNREGISTERED) + len(_SEARCH)
    )


def run_every_tool(tmp_path: Path) -> list[str]:
    """Call every agent-tool plugin and return one result line each."""
    _check_catalog()
    lines: list[str] = []

    def record(capability: str, label: str) -> None:
        lines.append(f"{capability} {label}")

    written = _load(
        tmp_path,
        "tools.write",
        {"file_path": NOTE, "content": f"before {TOKEN}\n"},
    )
    assert TOKEN in Path(written["path"]).read_text(encoding="utf-8")
    record("tools.write", "ok")

    edited = _load(
        tmp_path,
        "tools.edit",
        {
            "file_path": NOTE,
            "old_string": f"before {TOKEN}",
            "new_string": f"after {TOKEN}",
        },
    )
    assert edited["replacements"] == 1
    record("tools.edit", "ok")

    read = _load(tmp_path, "tools.read", {"file_path": NOTE})
    assert TOKEN in read["content"]
    record("tools.read", "ok")

    found = _load(tmp_path, "tools.glob", {"pattern": NOTE, "path": "."})
    assert NOTE in found["files"]
    record("tools.glob", "ok")

    matched = _load(tmp_path, "tools.grep", {"pattern": TOKEN, "path": NOTE})
    assert matched["count"] >= 1
    record("tools.grep", "ok")

    image = tmp_path / "dot.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    pictured = _load(tmp_path, "tools.read_image", {"file_path": "dot.png"})
    assert pictured["mediaType"] == "image/png"
    assert pictured["bytes"] > 0
    record("tools.read_image", "ok")

    created = _load(
        tmp_path,
        "tools.str_replace_editor",
        {"command": "create", "path": "made.txt", "file_text": f"{TOKEN}\n"},
    )
    assert created["command"] == "create"
    viewed = _load(
        tmp_path,
        "tools.str_replace_editor",
        {"command": "view", "path": "made.txt"},
    )
    assert TOKEN in viewed["content"]
    record("tools.str_replace_editor", "ok")

    record("tools.bash", _bash(tmp_path, "tools.bash"))
    record("tools.bash_persistent", _bash(tmp_path, "tools.bash_persistent"))

    listed = _load(tmp_path, "tools.mcp_tool_manager", {"name": "list"})
    assert listed["tools"] == []
    record("tools.mcp_tool_manager", "list")

    host_calls = (
        ("tools.terminal_open", {"type": "bash"}),
        ("tools.terminal_send", {"sessionId": "s", "text": "hi"}),
        ("tools.terminal_read_session", {"sessionId": "s"}),
        ("tools.terminal_list", {}),
        ("tools.terminal_signal", {"sessionId": "s", "signal": "SIGINT"}),
        ("tools.terminal_close_session", {"sessionId": "s"}),
        ("tools.ask_user", {"questions": [{"id": "q", "question": "continue?"}]}),
    )
    for capability, body in host_calls:
        _needs_host(tmp_path, capability, body)
        record(capability, "needs-host")

    clean = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONUTF8": "1"}
    for key in _SEARCH_KEYS.values():
        clean.pop(key, None)
    for capability, key_name in sorted(_SEARCH_KEYS.items()):
        parsed = _tool_result(
            _invoke(tmp_path, capability, {"query": "微服务"}, env=clean)
        )
        assert parsed["success"] is False, parsed
        assert key_name in str(parsed.get("error")), parsed
        record(capability, "needs-key")

    ddgs_body = {"query": "微服务"}
    try:
        import ddgs as _ddgs_package  # noqa: F401
    except ImportError:
        _ddgs_package = None
    else:
        ddgs_body = {"query": ""}
    ddgs = _tool_result(_invoke(tmp_path, "tools.ddgs", ddgs_body, env=clean))
    assert ddgs["success"] is False, ddgs
    if _ddgs_package is None:
        assert "ddgs" in str(ddgs.get("error")).lower(), ddgs
        record("tools.ddgs", "needs-package")
    else:
        assert "query" in str(ddgs.get("error")), ddgs
        record("tools.ddgs", "installed")

    for capability in sorted(_UNREGISTERED):
        _unknown(tmp_path, capability)
        record(capability, "unknown")

    recorded = {line.split()[0] for line in lines}
    assert recorded == _READY | _EXPLAINED | _MCP | _UNREGISTERED | _SEARCH
    lines.append("ok")
    return lines


def main() -> int:
    """Run the file tools, then every agent-tool plugin."""
    print("linope load tools.write cap tool")
    print("linope load tools.edit cap tool")
    print("linope load tools.read cap tool")
    print("linope load tools.glob cap tool")
    print("linope load tools.grep cap tool")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        try:
            test_linope_load_runs_file_tools(path)
            for line in run_every_tool(path):
                print(line)
        except AssertionError as error:
            print(error)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
