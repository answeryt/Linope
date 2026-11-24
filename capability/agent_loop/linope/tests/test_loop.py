"""The loop writes command lines. A stand-in door returns the kernel's text."""

import json
from io import StringIO

import pytest

from capability.agent_loop.linope.loop import CommandResult, Loop


def _drive(loop: Loop, question: str) -> str:
    """Run one turn the way the door does, for a turn that does not fork."""

    loop.prepare(question)
    while True:
        step = loop.step()
        if step.get("forks") or step.get("await"):
            raise RuntimeError("The kernel runs these tools")
        line = str(step.get("line") or "")
        if step.get("pc") == "wait_tool" and not line:
            reply = loop._miss or CommandResult()
        else:
            reply = loop.submit(line)
        if step.get("pc") == "ask_model" and reply.error:
            raise RuntimeError(reply.error)
        done = loop.land(reply)
        if done is not None:
            return done


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

    answer = _drive(
        Loop(_settings(["tools.glob"]), submit, catalog=_catalog(), identity="You are the linope agent."),
        "这个目录里有哪些文件？",
    )

    assert answer == "目录里有 README.md 和一个 src 文件夹。"
    assert "process start tools.glob" in lines
    assert 'load tool 8 -- {"pattern": "*"}' in lines
    assert lines[-1].startswith("model run -- ")
    assert "--share" not in "\n".join(lines)


def test_a_tool_call_keeps_arguments_that_arrive_as_text() -> None:
    lines: list[str] = []

    def submit(line: str) -> CommandResult:
        lines.append(line)
        if line.startswith("model use "):
            return CommandResult(result={"configured": True})
        if line == "process start tools.glob":
            return CommandResult(result={"processes": [{"pid": 8, "capability": "tools.glob"}]})
        if line == 'load tool 8 -- {"pattern": "*"}':
            return CommandResult(result="README.md")
        if line.startswith("model run -- "):
            if line.count("model run -- ") and "README.md" not in line:
                return CommandResult(result={
                    "type": "model_turn",
                    "blocks": [{
                        "type": "tool-call",
                        "id": "call-1",
                        "name": "tools_glob",
                        "arguments": "{\"pattern\": \"*\"}",
                    }],
                })
            return CommandResult(result="目录里有 README.md。")
        raise AssertionError(line)

    answer = _drive(Loop(_settings(["tools.glob"]), submit, catalog=_catalog(), identity=""), "有哪些文件？")

    assert answer == "目录里有 README.md。"
    assert 'load tool 8 -- {"pattern": "*"}' in lines


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

    answer = _drive(
        Loop(_settings(["tools.glob"]), submit, catalog=_catalog(), identity="You are the linope agent."),
        "这个目录里有哪些文件？",
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

    answer = _drive(Loop(_settings(["tools.read"]), submit, catalog=_catalog(), identity=""), "read note.txt")

    assert answer == "The file is blocked."
    assert asked["n"] == 2


def test_a_second_question_sees_the_first_turn() -> None:
    saved: list[dict] = []
    bodies: list[dict] = []

    def submit(line: str) -> CommandResult:
        if line.startswith("model use "):
            return CommandResult(result={"configured": True})
        if line.startswith("show "):
            return CommandResult(result={"memory": {"items": saved}})
        if line.startswith("model run -- "):
            bodies.append(json.loads(line.split(" -- ", 1)[1]))
            return CommandResult(result="hello")
        raise AssertionError(line)

    loop = Loop(_settings(["tools.glob"]), submit, catalog=_catalog(), identity="")
    loop.bind(41, "41")
    loop._model_ready = True
    assert _drive(loop, "first") == "hello"
    assert loop.memory_rows() == []
    saved.extend([
        {"kind": "user", "content": "first", "seq": 1, "real": "message/0"},
        {"kind": "model", "content": "hello", "seq": 2, "real": "message/1"},
    ])
    assert _drive(loop, "second") == "hello"
    messages = bodies[-1]["messages"]
    assert messages[-3] == {"role": "user", "content": "first"}
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
    assert [item["id"] for item in forks["forks"]] == ["", ""]
    assert [item["registers"]["call_id"] for item in forks["forks"]] == ["call-1", "call-2"]
    assert "pc" not in forks["forks"][0]
    loop.land_signal([{"call_id": "call-2", "result": "sunny", "error": ""}])
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
    assert [item["registers"]["call_id"] for item in forks["forks"]] == ["call-1", "call-2"]
    loop.land_signal([{"call_id": "call-2", "result": "sunny", "error": ""}])
    assert [call_id for call_id, _name in loop._unanswered()] == ["call-1"]
    weather = loop.step()
    assert weather["pc"] == "ask_model"
    weather_messages = json.dumps(json.loads(weather["line"].split(" -- ", 1)[1])["messages"], ensure_ascii=False)
    assert "sunny" in weather_messages
    assert "call-1" not in weather_messages
    assert loop.land(CommandResult(result="先看到晴。")) is None
    assert loop.step().get("await") is True
    loop.land_signal([{"call_id": "call-1", "result": "note", "error": ""}])
    reading = loop.step()
    assert reading["pc"] == "ask_model"
    reading_messages = json.loads(reading["line"].split(" -- ", 1)[1])["messages"]
    assert reading_messages[-1] == {"role": "user", "content": "tools.read finished:\nnote"}
    assert "call-1" not in json.dumps(reading_messages, ensure_ascii=False)
    assert loop.land(CommandResult(result="明天记得带伞。")) == "明天记得带伞。"


def test_a_queued_signal_lands_before_the_model_is_asked_again() -> None:
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
    assert loop.land(CommandResult(result=json.dumps({
        "type": "model_turn",
        "blocks": [
            {"type": "tool-call", "id": "call-1", "name": "tools.read", "arguments": {"file_path": "note.txt"}},
            {"type": "tool-call", "id": "call-2", "name": "tools.weather", "arguments": {"day": "today"}},
        ],
    }, ensure_ascii=False))) is None
    loop.step()
    loop.land_signal([{"call_id": "call-2", "result": "sunny", "error": ""}])
    assert loop.step()["pc"] == "ask_model"
    assert loop.land(CommandResult(result={
        "type": "signals",
        "items": [{"call_id": "call-1", "result": "note", "error": ""}],
    })) is None
    messages = json.loads(loop.step()["line"].split(" -- ", 1)[1])["messages"]
    assert {"role": "tool", "name": "tools.weather", "tool_call_id": "call-2", "content": "sunny"} in messages
    assert {"role": "tool", "name": "tools.read", "tool_call_id": "call-1", "content": "note"} in messages
    assert not any("finished:" in str(item.get("content") or "") for item in messages)
    assert loop.land(CommandResult(result="目录里有这些。")) == "目录里有这些。"


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
    loop.step()
    loop.land_signal([{"call_id": "call-1", "result": "tools.read", "error": ""}])
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
        json.dumps({"operation": "load", "kind": "message", "thread": "4", "body": "hi"}),
        json.dumps({"event": "command_result", "thread": "4", "result": "", "error": ""}),
        json.dumps({
            "event": "command_result",
            "thread": "4",
            "result": {"facts": {"pid": 4}, "links": []},
            "error": "",
        }),
        json.dumps({"event": "command_result", "thread": "4", "result": "hello", "error": ""}),
        json.dumps({"event": "command_result", "thread": "4", "result": "", "error": ""}),
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
    assert lines[0]["threads"] is True
    assert lines[-1]["event"] == "result"
    assert lines[-1]["result"] == "hello"
    assert lines[-1]["rows"] == []
    assert lines[-1]["thread"] == "4"
    assert any(item.get("event") == "command" and item.get("line") == "show 4" for item in lines)


def test_an_open_turn_does_not_see_another_open_turn() -> None:
    def submit(line: str) -> CommandResult:
        if line.startswith("show ") or line.startswith("model use "):
            return CommandResult(result={})
        raise AssertionError(line)

    loop = Loop(_settings(["tools.read"]), submit, catalog=_catalog(), identity="")
    loop.bind(41, "41")
    loop._model_ready = True
    loop._pids["tools.read"] = 8
    loop.prepare("read")
    assert loop.land(CommandResult(result=_turn("tools.read", {"file_path": "note.txt"}))) is None
    other = loop.open_turn("41.t1")
    other.prepare("hello")
    assert "read" not in json.dumps(other.messages, ensure_ascii=False)
    assert other.land(CommandResult(result="hi")) == "hi"
    assert "hello" not in json.dumps(loop.messages, ensure_ascii=False)


def test_two_tools_that_share_a_call_name_fail() -> None:
    catalog = {
        "tools.a.b": {"schemas": [{"name": "b", "description": "", "parameters": {}}]},
        "tools.a_b": {"schemas": [{"name": "b", "description": "", "parameters": {}}]},
    }
    with pytest.raises(ValueError, match="tools_a_b"):
        Loop(_settings(["tools.a.b", "tools.a_b"]), lambda _line: CommandResult(), catalog=catalog, identity="")


def test_a_configured_tool_without_a_schema_fails() -> None:
    with pytest.raises(ValueError, match="tools.other"):
        Loop(
            _settings(["tools.other"]),
            lambda _line: CommandResult(),
            catalog={"tools.other": {}},
            identity="",
        )


def _hub_rows() -> list[dict]:
    return [{
        "name": "time-get_current_time",
        "description": "Current time",
        "parameters": {
            "type": "object",
            "properties": {"timezone": {"type": "string"}},
        },
    }, {
        "name": "fetch-fetch",
        "description": "Fetch a page",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    }]


def test_the_hub_name_is_not_handed_to_the_loop() -> None:
    from capability.agent_loop.linope.__main__ import _without_hub

    settings = _without_hub(_settings(["tools.read", "tools.mcp_tool_manager"]))
    loop = Loop(settings, lambda _line: CommandResult(), catalog=_catalog(), identity="")
    assert [tool.capability for tool in loop.tools] == ["tools.read"]


def test_mcp_tools_fail_when_the_hub_is_down() -> None:
    from capability.agent_loop.linope.__main__ import _RemoteTools

    calls = {"n": 0}

    def discover() -> list[dict]:
        calls["n"] += 1
        raise RuntimeError("MCPHub is not running at http://127.0.0.1:3000/mcp")

    loop = Loop(_settings([]), lambda _line: CommandResult(), catalog={}, identity="")
    remote = _RemoteTools("tools.mcp_tool_manager", discover)
    with pytest.raises(RuntimeError, match="MCPHub is not running"):
        remote.install(loop)
    with pytest.raises(RuntimeError, match="MCPHub is not running"):
        remote.install(loop)
    assert calls["n"] == 1
    assert loop.tools == ()


def test_a_hub_tool_is_called_with_its_name() -> None:
    from capability.agent_loop.linope.__main__ import _RemoteTools

    lines: list[str] = []
    asked = {"n": 0}

    def submit(line: str) -> CommandResult:
        lines.append(line)
        if line == "process start tools.mcp_tool_manager":
            return CommandResult(result={"processes": [{"pid": 12, "capability": "tools.mcp_tool_manager"}]})
        if line == "model use model.openai_chat_model":
            return CommandResult(result={"configured": True})
        if line.startswith("model run -- "):
            asked["n"] += 1
            if asked["n"] == 1:
                assert "time-get_current_time" in line
                assert "fetch-fetch" in line
                return CommandResult(result=_turn("time-get_current_time", {"timezone": "UTC"}))
            return CommandResult(result="现在是 UTC 零点。")
        if line == 'load tool 12 -- {"name": "time-get_current_time", "arguments": {"timezone": "UTC"}}':
            return CommandResult(result="2026-11-20T00:00:00Z")
        raise AssertionError(line)

    loop = Loop(_settings([]), submit, catalog={}, identity="")
    remote = _RemoteTools("tools.mcp_tool_manager", _hub_rows)
    remote.install(loop)
    remote.install(loop)
    answer = _drive(loop, "现在几点？")

    assert answer == "现在是 UTC 零点。"
    assert lines[0] == "model use model.openai_chat_model"
    body = json.loads(lines[1].split(" -- ", 1)[1])
    assert [tool["name"] for tool in body["tools"]] == ["time-get_current_time", "fetch-fetch"]
    assert '"name": "list"' not in "\n".join(lines)
    assert lines.count("process start tools.mcp_tool_manager") == 1
    assert lines.index("process start tools.mcp_tool_manager") > 1


def test_a_turn_returns_the_tool_rows_it_produced() -> None:
    asked = {"n": 0}

    def submit(line: str) -> CommandResult:
        if line.startswith("show ") or line.startswith("model use "):
            return CommandResult(result={})
        if line.startswith("model run -- "):
            asked["n"] += 1
            if asked["n"] == 1:
                return CommandResult(result=_turn("tools.read", {"file_path": "note.txt"}))
            return CommandResult(result="The file is note.")
        if line.startswith("load tool "):
            return CommandResult(result="note")
        raise AssertionError(line)

    loop = Loop(_settings(["tools.read"]), submit, catalog=_catalog(), identity="")
    loop.bind(4, "4")
    loop._model_ready = True
    loop._pids["tools.read"] = 8
    assert _drive(loop, "read note") == "The file is note."
    rows = loop.memory_rows()
    assert [row["kind"] for row in rows] == ["model", "tool"]
    model = json.loads(rows[0]["content"])
    assert model["blocks"][-1]["id"] == "call-1"
    assert model["blocks"][-1]["name"] == "tools.read"
    assert json.loads(rows[1]["content"]) == {
        "type": "tool-result",
        "request_id": "call-1",
        "name": "tools.read",
        "output": "note",
    }


def test_a_new_turn_reads_tool_rows_and_drops_the_unfinished_question() -> None:
    model_row = json.dumps({
        "type": "model_turn",
        "blocks": [{
            "type": "tool-call",
            "id": "call-1",
            "name": "tools.read",
            "arguments": {"file_path": "note.txt"},
        }],
        "finish_reason": "stop",
    }, ensure_ascii=False)
    tool_row = json.dumps({
        "type": "tool-result",
        "request_id": "call-1",
        "name": "tools.read",
        "output": "note",
    }, ensure_ascii=False)
    saved = [
        {"kind": "user", "content": "read note", "seq": 1, "real": "message/0"},
        {"kind": "model", "content": model_row, "seq": 2, "real": "message/1"},
        {"kind": "tool", "content": tool_row, "seq": 3, "real": "artifact/0"},
        {"kind": "model", "content": "The file is note.", "seq": 4, "real": "message/2"},
        {"kind": "user", "content": "again", "seq": 5, "real": "message/3"},
    ]
    bodies: list[dict] = []

    def submit(line: str) -> CommandResult:
        if line.startswith("show "):
            return CommandResult(result={"memory": {"items": saved}})
        if line.startswith("model run -- "):
            bodies.append(json.loads(line.split(" -- ", 1)[1]))
            return CommandResult(result="ok")
        raise AssertionError(line)

    loop = Loop(_settings(["tools.read"]), submit, catalog=_catalog(), identity="")
    loop.bind(5, "5")
    loop._model_ready = True
    assert _drive(loop, "again") == "ok"
    assert bodies[0]["messages"] == [
        {"role": "user", "content": "read note"},
        {
            "role": "assistant",
            "content": [{
                "type": "tool-call",
                "id": "call-1",
                "name": "tools.read",
                "arguments": {"file_path": "note.txt"},
            }],
        },
        {"role": "tool", "content": "note", "tool_call_id": "call-1", "name": "tools.read"},
        {"role": "assistant", "content": "The file is note."},
        {"role": "user", "content": "again"},
    ]
