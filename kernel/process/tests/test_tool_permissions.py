"""Tool ceilings cannot be widened by a startup mode or a session mode."""

from pathlib import Path

from kernel.environment.session_mode import remember_mode
from kernel.process.profiles import tool_effect, tool_with_workspace
from kernel.process.process_manager.tool_dispatch import tool_request


def _mode(declaration) -> str:
    sandbox = next(item for item in declaration.resources if item.kind == "sandbox")
    return str(sandbox.call_params["mode"])


def test_effects_match_the_tool_names() -> None:
    assert tool_effect("tools.read") == "read"
    assert tool_effect("tools.grep") == "read"
    assert tool_effect("tools.write") == "write"
    assert tool_effect("tools.str_replace_editor") == "write"
    assert tool_effect("tools.bash") == "command"
    assert tool_effect("tools.terminal_open") == "command"


def test_a_read_tool_cannot_be_raised(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LINOPE_SESSION_ROOT", str(tmp_path))
    declaration = tool_with_workspace(
        "tools.read",
        (("mode", "danger-full-access"),),
    )
    assert _mode(declaration) == "read-only"


def test_a_write_tool_defaults_to_the_workspace_and_can_be_explicitly_opened(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LINOPE_SESSION_ROOT", str(tmp_path))
    assert _mode(tool_with_workspace("tools.write", ())) == "workspace-write"
    opened = tool_with_workspace("tools.edit", (("mode", "danger-full-access"),))
    assert _mode(opened) == "danger-full-access"


def test_session_mode_narrows_a_later_tool(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LINOPE_SESSION_ROOT", str(tmp_path))
    remember_mode(str(tmp_path), "read-only")
    assert _mode(tool_with_workspace("tools.write", ())) == "read-only"
    assert _mode(tool_with_workspace("tools.bash", (("mode", "danger-full-access"),))) == "read-only"
    assert _mode(tool_with_workspace("tools.read", ())) == "read-only"


def test_tool_request_rejects_a_hidden_tool() -> None:
    try:
        tool_request("write", {}, permission="read-only", capabilities=["write"])
    except PermissionError as exc:
        assert "tools.write" in str(exc)
    else:
        raise AssertionError("expected the write tool to be hidden")
