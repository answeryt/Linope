"""The session file keeps addresses. The body stays in memory."""

import json
from pathlib import Path

import pytest

from capability.session.session import SessionError, SessionLog


def _log(root: Path) -> SessionLog:
    return SessionLog(root, "chat", clock=lambda: "2026-11-09T00:00:00Z", ids=lambda: "s1")


def test_the_index_records_the_address_and_leaves_the_body_out(tmp_path: Path) -> None:
    log = _log(tmp_path)
    added = log.note([{
        "seq": 1,
        "real": "message/0",
        "kind": "user",
        "content": "secret words",
        "address": "message/0",
    }])

    text = log.path.read_text(encoding="utf-8")
    assert "secret words" not in text
    assert "content" not in text
    assert "pid" not in text
    assert added[0].real == "message/0"
    lines = [json.loads(line) for line in text.splitlines()]
    assert lines[0] == {"id": "s1", "scope": "chat", "created": "2026-11-09T00:00:00Z"}
    assert lines[1] == {"seq": 1, "real": "message/0", "kind": "user"}


def test_a_second_note_appends_and_keeps_the_header(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.note([{"seq": 1, "real": "message/0", "kind": "user", "content": "one"}])
    again = SessionLog(tmp_path, "chat", clock=lambda: "later", ids=lambda: "other")
    again.note([{"seq": 2, "real": "message/1", "kind": "model", "content": "two"}])

    lines = [json.loads(line) for line in log.path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["id"] == "s1"
    assert [item["real"] for item in lines[1:]] == ["message/0", "message/1"]
    assert "one" not in log.path.read_text(encoding="utf-8")
    assert "two" not in log.path.read_text(encoding="utf-8")


def test_a_tool_call_is_recorded_when_the_new_row_is_that_call(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.note(
        [{"seq": 4, "real": "artifact/1", "kind": "tool", "content": "README"}],
        calls=[("call-1", "tools.glob")],
    )

    line = json.loads(log.path.read_text(encoding="utf-8").splitlines()[-1])
    assert line == {
        "seq": 4,
        "real": "artifact/1",
        "kind": "tool",
        "tool_call_id": "call-1",
        "name": "tools.glob",
    }
    assert "README" not in log.path.read_text(encoding="utf-8")


def test_several_new_rows_pair_with_several_calls_in_order(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.note(
        [
            {"seq": 3, "real": "artifact/1", "kind": "tool", "content": "sunny"},
            {"seq": 2, "real": "artifact/0", "kind": "tool", "content": "note"},
        ],
        calls=[("call-1", "tools.read"), ("call-2", "tools.weather")],
    )

    lines = [json.loads(line) for line in log.path.read_text(encoding="utf-8").splitlines()[1:]]
    assert [(item["real"], item["tool_call_id"]) for item in lines] == [
        ("artifact/0", "call-1"),
        ("artifact/1", "call-2"),
    ]


def test_one_call_among_other_new_rows_marks_only_the_tool_row(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.note(
        [
            {"seq": 1, "real": "message/0", "kind": "user", "content": "hi"},
            {"seq": 2, "real": "artifact/0", "kind": "tool", "content": "body"},
        ],
        calls=[("call-1", "tools.read")],
    )

    lines = [json.loads(line) for line in log.path.read_text(encoding="utf-8").splitlines()[1:]]
    assert "tool_call_id" not in lines[0]
    assert lines[1]["tool_call_id"] == "call-1"
    assert lines[1]["name"] == "tools.read"


def test_a_real_name_already_indexed_is_not_written_again(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.note([{"seq": 1, "real": "system", "kind": "system", "content": "rules"}])
    log.note([
        {"seq": 5, "real": "system", "kind": "system", "content": "rules again"},
        {"seq": 4, "real": "message/0", "kind": "user", "content": "later"},
    ])
    log.note([{"seq": 2, "real": "message/1", "kind": "user", "content": "old"}])

    lines = [json.loads(line) for line in log.path.read_text(encoding="utf-8").splitlines()[1:]]
    assert [item["real"] for item in lines] == ["system", "message/0"]
    assert "rules" not in log.path.read_text(encoding="utf-8")
    assert "later" not in log.path.read_text(encoding="utf-8")


def test_messages_are_rebuilt_from_the_reader(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.note([{"seq": 1, "real": "message/0", "kind": "user"}])
    log.note(
        [{"seq": 2, "real": "artifact/0", "kind": "tool"}],
        calls=[("call-1", "tools.read")],
    )

    def read(real: str) -> dict | None:
        if real == "message/0":
            return {"real": real, "content": "hello"}
        if real == "artifact/0":
            return {"real": real, "content": "note"}
        return None

    assert log.messages(read) == [
        {"role": "user", "content": "hello"},
        {"role": "tool", "content": "note", "tool_call_id": "call-1", "name": "tools.read"},
    ]


def test_a_missing_row_fails_the_session(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.note([{"seq": 1, "real": "message/0", "kind": "user"}])

    with pytest.raises(SessionError, match="message/0"):
        log.messages(lambda _real: None)


def test_the_session_module_does_not_import_the_kernel() -> None:
    source = (Path(__file__).resolve().parents[1] / "session.py").read_text(encoding="utf-8")
    assert "import kernel" not in source
    assert "from kernel" not in source
