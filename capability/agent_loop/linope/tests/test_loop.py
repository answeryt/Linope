"""The loop writes command lines. A stand-in door returns the kernel's text."""

import json
from io import StringIO
from pathlib import Path

import pytest

from capability.agent_loop.linope.loop import CommandResult, Loop
from capability.session.session import SessionError, SessionLog


def _catalog() -> dict:
    return {
        "tools.glob": {
            "schemas": [{
                "name": "glob",
                "description": "Find files.",
                "parameters": {
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}},
                    "required": ["pattern"],
                },
            }],
        },
        "tools.read": {
            "schemas": [{
                "name": "read",
                "description": "Read a file.",
                "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}},
            }],
        },
    }


def _settings(tools: list[str]) -> dict:
    return {"model": "model.openai_chat_model", "tools": tools}


def _turn(name: str, arguments: dict) -> str:
    return json.dumps({
        "type": "model_turn",
        "blocks": [{
            "type": "tool-call",
            "id": "call-1",
            "name": name,
            "arguments": arguments,
        }],
    }, ensure_ascii=False)


def test_a_tool_call_runs_and_the_next_reply_is_the_answer() -> None:
    lines: list[str] = []
    asked = {"n": 0}

    def submit(line: str) -> CommandResult:
        lines.append(line)
        if line == "model use model.openai_chat_model":
            return CommandResult(result={"configured": True})
        if line.startswith("model run -- "):
            asked["n"] += 1
            if asked["n"] == 1:
                return CommandResult(result=_turn("tools_glob", {"pattern": "*"}))
            return CommandResult(result="目录里有 README.md 和一个 src 文件夹。")
        if line == "process start tools.glob":
            return CommandResult(result={"processes": [{"pid": 8, "capability": "tools.glob"}]})
        if line == 'load tool 8 -- {"pattern": "*"}':
            return CommandResult(result="README.md\nsrc/")
        raise AssertionError(line)

    answer = Loop(_settings(["tools.glob"]), submit, catalog=_catalog(), identity="You are the linope agent.").ask(
        "这个目录里有哪些文件？"
    )

    assert answer == "目录里有 README.md 和一个 src 文件夹。"
    assert "process start tools.glob" in lines
    assert 'load tool 8 -- {"pattern": "*"}' in lines
    assert lines[-1].startswith("model run -- ")
    assert "--share" not in "\n".join(lines)


def test_a_text_reply_does_not_start_a_tool() -> None:
    lines: list[str] = []

    def submit(line: str) -> CommandResult:
        lines.append(line)
        if line.startswith("model use "):
            return CommandResult(result={"configured": True})
        if line.startswith("model run -- "):
            body = json.loads(line.split(" -- ", 1)[1])
            assert body["messages"][0]["content"] == "You are the linope agent."
            assert body["tools"][0]["name"] == "tools_glob"
            return CommandResult(result="目录里有 README.md。")
        raise AssertionError(line)

    answer = Loop(_settings(["tools.glob"]), submit, catalog=_catalog(), identity="You are the linope agent.").ask(
        "这个目录里有哪些文件？"
    )

    assert answer == "目录里有 README.md。"
    assert not any(line.startswith("process start tools.") for line in lines)


def test_a_tool_error_is_given_back_to_the_model() -> None:
    asked = {"n": 0}

    def submit(line: str) -> CommandResult:
        if line.startswith("model use "):
            return CommandResult(result={"configured": True})
        if line == "process start tools.read":
            return CommandResult(result={"processes": [{"pid": 9, "capability": "tools.read"}]})
        if line.startswith("load tool "):
            return CommandResult(error="read-only file system")
        if line.startswith("model run -- "):
            asked["n"] += 1
            if asked["n"] == 1:
                return CommandResult(result=_turn("tools.read", {"file_path": "note.txt"}))
            body = json.loads(line.split(" -- ", 1)[1])
            tool = next(message for message in body["messages"] if message["role"] == "tool")
            assert tool["content"] == "read-only file system"
            assert tool["tool_call_id"] == "call-1"
            return CommandResult(result="The file is blocked.")
        raise AssertionError(line)

    answer = Loop(_settings(["tools.read"]), submit, catalog=_catalog(), identity="").ask("read note.txt")

    assert answer == "The file is blocked."
    assert asked["n"] == 2


def test_a_second_question_sees_the_first_turn() -> None:
    bodies: list[dict] = []

    def submit(line: str) -> CommandResult:
        if line.startswith("model use "):
            return CommandResult(result={"configured": True})
        if line.startswith("model run -- "):
            bodies.append(json.loads(line.split(" -- ", 1)[1]))
            return CommandResult(result="hello")
        raise AssertionError(line)

    loop = Loop(_settings(["tools.glob"]), submit, catalog=_catalog(), identity="")
    assert loop.ask("first") == "hello"
    assert loop.ask("second") == "hello"
    messages = bodies[1]["messages"]
    assert messages[-2] == {"role": "assistant", "content": "hello"}
    assert messages[-1] == {"role": "user", "content": "second"}


def test_two_tool_calls_open_two_threads() -> None:
    catalog = _catalog()
    catalog["tools.weather"] = {
        "schemas": [{
            "name": "weather",
            "description": "Weather.",
            "parameters": {"type": "object", "properties": {"day": {"type": "string"}}},
        }],
    }

    def submit(line: str) -> CommandResult:
        if line.startswith("show "):
            return CommandResult(result="{}")
        raise AssertionError(line)

    loop = Loop(
        {"model": "model.openai_chat_model", "tools": ["tools.read", "tools.weather"]},
        submit,
        catalog=catalog,
        identity="",
    )
    loop.bind(41, "41")
    assert loop.thread_id == "41"
    loop._model_ready = True
    loop._pids["tools.read"] = 8
    loop._pids["tools.weather"] = 9
    loop.prepare("读一下 note.txt，再查一下今天的天气。")
    assert loop.land(CommandResult(result=json.dumps({
        "type": "model_turn",
        "blocks": [
            {"type": "tool-call", "id": "call-1", "name": "tools.read", "arguments": {"file_path": "note.txt"}},
            {"type": "tool-call", "id": "call-2", "name": "tools.weather", "arguments": {"day": "today"}},
        ],
    }, ensure_ascii=False))) is None
    forks = loop.step()
    assert [item["id"] for item in forks["forks"]] == ["41.2", "41.3"]
    assert "pc" not in forks["forks"][0]
    loop.note_issued(item["id"] for item in forks["forks"])
    loop.land_signal([{"thread": "41.3", "result": "sunny", "error": ""}])
    assert loop.step()["pc"] == "ask_model"


def test_the_first_signal_asks_the_model_before_the_other_tool() -> None:
    catalog = _catalog()
    catalog["tools.weather"] = {
        "schemas": [{
            "name": "weather",
            "description": "Weather.",
            "parameters": {"type": "object", "properties": {"day": {"type": "string"}}},
        }],
    }

    def submit(line: str) -> CommandResult:
        if line.startswith("show "):
            return CommandResult(result="{}")
        raise AssertionError(line)

    loop = Loop(
        {"model": "model.openai_chat_model", "tools": ["tools.read", "tools.weather"]},
        submit,
        catalog=catalog,
        identity="",
    )
    loop.bind(41, "41")
    loop._model_ready = True
    loop._pids["tools.read"] = 8
    loop._pids["tools.weather"] = 9
    loop.prepare("今天天气怎么样，帮我分析 Linope。")
    opening = loop.step()
    assert opening["pc"] == "ask_model"
    assert loop.land(CommandResult(result=json.dumps({
        "type": "model_turn",
        "blocks": [
            {"type": "tool-call", "id": "call-1", "name": "tools.read", "arguments": {"file_path": "note.txt"}},
            {"type": "tool-call", "id": "call-2", "name": "tools.weather", "arguments": {"day": "today"}},
        ],
    }, ensure_ascii=False))) is None
    forks = loop.step()
    assert [item["id"] for item in forks["forks"]] == ["41.2", "41.3"]
    loop.note_issued(item["id"] for item in forks["forks"])
    loop.land_signal([{"thread": "41.3", "result": "sunny", "error": ""}])
    assert [item["id"] for item in loop._forks] == ["41.2"]
    weather = loop.step()
    assert weather["pc"] == "ask_model"
    weather_messages = json.dumps(json.loads(weather["line"].split(" -- ", 1)[1])["messages"], ensure_ascii=False)
    assert "sunny" in weather_messages
    assert "call-1" not in weather_messages
    assert loop.land(CommandResult(result="先看到晴。")) is None
    assert loop.step().get("await") is True
    loop.land_signal([{"thread": "41.2", "result": "note", "error": ""}])
    reading = loop.step()
    assert reading["pc"] == "ask_model"
    reading_messages = json.loads(reading["line"].split(" -- ", 1)[1])["messages"]
    assert reading_messages[-1] == {"role": "user", "content": "tools.read finished:\nnote"}
    assert "call-1" not in json.dumps(reading_messages, ensure_ascii=False)
    assert loop.land(CommandResult(result="明天记得带伞。")) == "明天记得带伞。"


def test_the_next_model_line_keeps_the_reasoning() -> None:
    def submit(line: str) -> CommandResult:
        if line.startswith("show "):
            return CommandResult(result="{}")
        raise AssertionError(line)

    loop = Loop(
        {"model": "model.openai_chat_model", "tools": ["tools.read", "tools.glob"]},
        submit,
        catalog=_catalog(),
        identity="",
    )
    loop.bind(41, "41")
    loop._model_ready = True
    loop._pids["tools.read"] = 8
    loop._pids["tools.glob"] = 9
    loop.prepare("读配置，再找文件。")
    assert loop.land(CommandResult(result={
        "type": "model_turn",
        "blocks": [
            {"type": "reasoning", "text": "read the file first"},
            {"type": "tool-call", "id": "call-1", "name": "tools.read", "arguments": {"file_path": "capability/agent_loop/linope.json"}},
            {"type": "tool-call", "id": "call-2", "name": "tools.glob", "arguments": {"pattern": "*.json"}},
        ],
    })) is None
    forks = loop.step()
    loop.note_issued(item["id"] for item in forks["forks"])
    loop.land_signal([{"thread": forks["forks"][0]["id"], "result": "tools.read", "error": ""}])
    messages = json.loads(loop.step()["line"].split(" -- ", 1)[1])["messages"]
    assistant = next(item for item in messages if item["role"] == "assistant")
    assert assistant["reasoning_content"] == "read the file first"

    spoken = Loop(
        {"model": "model.openai_chat_model", "tools": ["tools.read"]},
        submit,
        catalog=_catalog(),
        identity="",
    )
    spoken._model_ready = True
    spoken.prepare("hi")
    assert spoken.land(CommandResult(result={
        "type": "model_turn",
        "blocks": [
            {"type": "reasoning", "text": "just answer"},
            {"type": "text", "text": "hello"},
        ],
    })) == "hello"
    assert spoken.messages[-1]["reasoning_content"] == "just answer"


def test_the_stdio_door_returns_the_model_text(monkeypatch) -> None:
    import capability.agent_loop.linope.__main__ as door

    inbound = StringIO("\n".join([
        json.dumps({
            "activation": {
                "pid": 4,
                "resource_context": {
                    "settings": {"model": "model.openai_chat_model", "tools": ["tools.glob"]},
                },
            },
        }),
        json.dumps({"operation": "load", "kind": "message", "body": "hi"}),
        json.dumps({"event": "command_result", "result": "", "error": ""}),
        json.dumps({
            "event": "command_result",
            "result": {"facts": {"pid": 4}, "links": []},
            "error": "",
        }),
        json.dumps({"event": "command_result", "result": "hello", "error": ""}),
        json.dumps({"event": "command_result", "result": "", "error": ""}),
    ]) + "\n")
    outbound = StringIO()
    monkeypatch.setattr(door.sys, "stdin", inbound)
    monkeypatch.setattr(door.sys, "stdout", outbound)

    door.main()

    lines = [json.loads(line) for line in outbound.getvalue().splitlines() if line.strip()]
    assert lines[0]["event"] == "ready"
    assert lines[0]["pid"] == 4
    assert any(
        item.get("event") == "command" and item["line"] == "model use model.openai_chat_model"
        for item in lines
    )
    assert lines[-1] == {"event": "result", "result": "hello"}
    assert any(item.get("event") == "command" and item.get("line") == "show 4" for item in lines)


def test_two_tools_that_share_a_call_name_fail() -> None:
    catalog = {
        "tools.a.b": {"schemas": [{"name": "b", "description": "", "parameters": {}}]},
        "tools.a_b": {"schemas": [{"name": "b", "description": "", "parameters": {}}]},
    }
    with pytest.raises(ValueError, match="tools_a_b"):
        Loop(_settings(["tools.a.b", "tools.a_b"]), lambda _line: CommandResult(), catalog=catalog, identity="")


def test_a_configured_tool_without_a_schema_fails() -> None:
    with pytest.raises(ValueError, match="tools.mcp_tool_manager"):
        Loop(
            _settings(["tools.mcp_tool_manager"]),
            lambda _line: CommandResult(),
            catalog={"tools.mcp_tool_manager": {}},
            identity="",
        )


def _row(seq: int, real: str, kind: str, content: str) -> dict:
    return {"seq": seq, "real": real, "kind": kind, "content": content, "address": real}


def _memory_page(items: list[dict]) -> str:
    return json.dumps({
        "facts": {"pid": 4},
        "links": [{"rel": "memory", "resource": "chat"}],
        "memory": {"system": "", "items": items},
    }, ensure_ascii=False)


def test_show_appends_new_addresses_and_a_new_process_reads_them(tmp_path: Path) -> None:
    user = _row(1, "message/0", "user", "read note")
    tool = _row(2, "artifact/0", "tool", "note")
    answer = _row(3, "message/1", "model", "The file is note.")
    pages = [
        _memory_page([user]),
        _memory_page([user]),
        _memory_page([user, tool]),
        _memory_page([user, tool]),
    ]
    shown = {"n": 0}

    def submit(line: str) -> CommandResult:
        if line.startswith("show "):
            page = pages[shown["n"]]
            shown["n"] += 1
            return CommandResult(result=page)
        if line.startswith("model run -- "):
            if shown["n"] < 3:
                return CommandResult(result=_turn("tools.read", {"file_path": "note.txt"}))
            return CommandResult(result="The file is note.")
        if line.startswith("load tool "):
            return CommandResult(result="note")
        raise AssertionError(line)

    first = Loop(_settings(["tools.read"]), submit, catalog=_catalog(), identity="", session_root=tmp_path)
    first.bind(4, "4.1")
    first._model_ready = True
    first._pids["tools.read"] = 8
    assert first.ask("read note") == "The file is note."

    text = (tmp_path / ".linope" / "sessions" / "chat.jsonl").read_text(encoding="utf-8")
    assert "read note" not in text
    assert "The file is note." not in text
    assert '"content"' not in text
    saved = [json.loads(line) for line in text.splitlines()]
    assert saved[0]["scope"] == "chat"
    assert "pid" not in saved[0]
    assert saved[1] == {"seq": 1, "real": "message/0", "kind": "user"}
    assert saved[2] == {
        "seq": 2,
        "real": "artifact/0",
        "kind": "tool",
        "tool_call_id": "call-1",
        "name": "tools.read",
    }

    bodies: list[dict] = []

    def resume(line: str) -> CommandResult:
        if line == "show 5 chat/message/0":
            return CommandResult(result=_memory_page([user]))
        if line == "show 5 chat/artifact/0":
            return CommandResult(result=_memory_page([tool]))
        if line == "show 5 chat/message/1":
            return CommandResult(result=_memory_page([answer]))
        if line == "show 5":
            return CommandResult(result=_memory_page([
                user,
                tool,
                answer,
                _row(4, "message/2", "user", "again"),
            ]))
        if line.startswith("model run -- "):
            bodies.append(json.loads(line.split(" -- ", 1)[1]))
            return CommandResult(result="ok")
        raise AssertionError(line)

    second = Loop(_settings(["tools.read"]), resume, catalog=_catalog(), identity="", session_root=tmp_path)
    second.bind(5, "5.1")
    second._model_ready = True
    assert second.ask("again") == "ok"
    assert bodies[0]["messages"] == [
        {"role": "user", "content": "read note"},
        {"role": "tool", "content": "note", "tool_call_id": "call-1", "name": "tools.read"},
        {"role": "assistant", "content": "The file is note."},
        {"role": "user", "content": "again"},
    ]


def test_a_missing_indexed_line_fails_before_the_model_is_asked(tmp_path: Path) -> None:
    SessionLog(tmp_path, "chat", clock=lambda: "2026-11-09T00:00:00Z", ids=lambda: "s1").note(
        [{"seq": 1, "real": "message/0", "kind": "user"}]
    )
    lines: list[str] = []

    def submit(line: str) -> CommandResult:
        lines.append(line)
        if line == "show 6":
            return CommandResult(result=_memory_page([_row(1, "message/0", "user", "hi")]))
        if line.startswith("show 6 "):
            return CommandResult(result="{}")
        raise AssertionError(line)

    loop = Loop(_settings(["tools.read"]), submit, catalog=_catalog(), identity="", session_root=tmp_path)
    loop.bind(6, "6.1")
    loop._model_ready = True
    with pytest.raises(SessionError, match="message/0"):
        loop.ask("next")
    assert lines == ["show 6", "show 6 chat/message/0"]


def test_a_foreign_index_is_set_aside_and_the_question_is_asked(tmp_path: Path) -> None:
    SessionLog(tmp_path, "chat", clock=lambda: "2026-11-09T00:00:00Z", ids=lambda: "s1").note([
        {"seq": 1, "real": "message/0", "kind": "user"},
        {"seq": 2, "real": "message/1", "kind": "model"},
    ])
    bodies: list[dict] = []

    def submit(line: str) -> CommandResult:
        if line == "show 8":
            return CommandResult(result=_memory_page([_row(1, "message/0", "user", "你好")]))
        if line == "show 8 chat/message/0":
            return CommandResult(result=_memory_page([_row(1, "message/0", "user", "你好")]))
        if line == "show 8 chat/message/1":
            return CommandResult(result="{}")
        if line.startswith("model run -- "):
            bodies.append(json.loads(line.split(" -- ", 1)[1]))
            return CommandResult(result="ok")
        raise AssertionError(line)

    loop = Loop(_settings(["tools.read"]), submit, catalog=_catalog(), identity="", session_root=tmp_path)
    loop.bind(8, "8.1")
    loop._model_ready = True
    assert loop.ask("你好") == "ok"
    assert bodies[0]["messages"] == [{"role": "user", "content": "你好"}]
    saved = [
        json.loads(line)
        for line in (tmp_path / ".linope" / "sessions" / "chat.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item.get("real") for item in saved[1:]] == ["message/0"]
