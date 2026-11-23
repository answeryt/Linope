"""Task steps travel on the same frontend-neutral event stream as other facts."""

from __future__ import annotations

import json
import threading
from io import StringIO

import kernel.command.server as server
from kernel.thread.task import close_process_threads


def _events(raw: str) -> list[dict]:
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def test_a_task_step_is_sent_before_the_command_returns(monkeypatch) -> None:
    incoming = StringIO(json.dumps({"command": "load message 41 -- 搜索天气"}) + "\n")
    outgoing = StringIO()
    monkeypatch.setattr(server.sys, "stdin", incoming)
    monkeypatch.setattr(server.sys, "stdout", outgoing)
    seen: dict[str, bool] = {}

    def command(self, raw: str, request_id: str = "") -> bool:
        del request_id
        from kernel.thread.task import open_process_threads

        close_process_threads(41)
        open_process_threads(41).first.move("ask_model", question="搜索天气")
        seen["during-command"] = "task.step" in outgoing.getvalue()
        del self, raw
        return False

    monkeypatch.setattr(server.KernelRuntime, "command", command)
    try:
        assert server.main() == 0
    finally:
        close_process_threads(41)
    assert seen["during-command"] is True
    kinds = [event["kind"] for event in _events(outgoing.getvalue())]
    assert "task.step" in kinds
    assert "session.started" in kinds
    assert "session.closed" in kinds


def test_ipc_forwards_each_task_without_mixing_registers(monkeypatch) -> None:
    incoming = StringIO(json.dumps({"command": "load message 41 -- 搜索天气"}) + "\n")
    outgoing = StringIO()
    monkeypatch.setattr(server.sys, "stdin", incoming)
    monkeypatch.setattr(server.sys, "stdout", outgoing)

    def command(self, raw: str, request_id: str = "") -> bool:
        del self, raw, request_id
        from kernel.thread.task import open_process_threads

        close_process_threads(41)
        table = open_process_threads(41)
        table.first.move("ask_model", question="搜索天气")
        table.open(
            registers={"tool": "search", "question": "天气"},
            program_counter="wait_tool",
        )
        table.open(
            registers={"tool": "read", "path": "note.txt"},
            program_counter="wait_tool",
        )
        return False

    monkeypatch.setattr(server.KernelRuntime, "command", command)
    try:
        assert server.main() == 0
    finally:
        close_process_threads(41)

    events = _events(outgoing.getvalue())
    assert all(event["version"] == 1 and event["kind"] and event["seq"] for event in events)
    steps = [item for item in events if item["kind"] == "task.step"]
    assert [item["seq"] for item in steps] == sorted(item["seq"] for item in steps)
    assert steps and steps[0]["seq"] >= 1
    by_id = {item["data"]["task_id"]: item["data"] for item in steps}
    assert by_id["41"]["registers"]["question"] == "搜索天气"
    assert by_id["41.2"]["registers"] == {"tool": "search", "question": "天气"}
    assert by_id["41.3"]["registers"] == {"tool": "read", "path": "note.txt"}
    assert "path" not in by_id["41.2"]["registers"]
    assert "天气" not in by_id["41.3"]["registers"].values()


def test_the_next_command_is_read_while_a_turn_is_open(monkeypatch) -> None:
    incoming = StringIO(
        "".join(
            json.dumps({"command": command, "id": request_id}) + "\n"
            for command, request_id in (("first", "a"), ("second", "b"), ("exit", "c"))
        )
    )
    outgoing = StringIO()
    monkeypatch.setattr(server.sys, "stdin", incoming)
    monkeypatch.setattr(server.sys, "stdout", outgoing)
    order: list[tuple[str, str]] = []
    busy = {"on": False}

    def command(self, raw: str, request_id: str = "") -> bool:
        del self
        order.append((raw, request_id))
        if raw == "first":
            busy["on"] = True
            return False
        if raw == "second":
            busy["on"] = False
            return False
        return raw == "exit"

    monkeypatch.setattr(server.KernelRuntime, "command", command)
    monkeypatch.setattr("kernel.scheduler.llm_scheduler.drive.Drive.step", lambda self: None)
    monkeypatch.setattr("kernel.scheduler.llm_scheduler.drive.Drive.busy", lambda self: busy["on"])
    worker = threading.Thread(target=server.main, daemon=True)
    worker.start()
    worker.join(3)
    assert not worker.is_alive()
    assert order == [("first", "a"), ("second", "b"), ("exit", "c")]


def test_a_command_without_a_value_still_completes(monkeypatch) -> None:
    incoming = StringIO(json.dumps({"command": "list", "id": "listed"}) + "\n")
    outgoing = StringIO()
    monkeypatch.setattr(server.sys, "stdin", incoming)
    monkeypatch.setattr(server.sys, "stdout", outgoing)

    def execute(self, text: str, request_id: str = "") -> None:
        del self, text, request_id
        return None

    monkeypatch.setattr(server.KernelRuntime, "_execute_text", execute)
    assert server.main() == 0

    completed = [
        event
        for event in _events(outgoing.getvalue())
        if event["kind"] == "command.completed" and event.get("request_id") == "listed"
    ]
    assert len(completed) == 1
    assert completed[0]["data"]["value"] is None
