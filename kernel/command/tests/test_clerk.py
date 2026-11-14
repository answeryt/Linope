"""One clerk can start more than one capability and still take the next line."""

from pathlib import Path

from kernel.command.events import CollectingEventSink
from kernel.command.process.clerk import KernelRuntime
from kernel.command.process.start import run as start_capability


def test_two_starts_return_before_the_window_closes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    sink = CollectingEventSink()
    clerk = KernelRuntime(sink)
    assert (
        clerk.serve(
            lines=[
                "model use model.openai_chat_model",
                "list",
                "process start tools.ask_user",
                "list",
                "exit",
            ]
        )
        == 0
    )
    started = [event for event in sink.events if event.kind == "process.started"]
    assert len(started) == 1
    assert started[0].data["capability"] == "tools.ask_user"
    assert all(event.pid for event in started)
    assert not any(event.kind == "done" for event in sink.events)


def test_create_writes_a_file_without_leaving_the_window(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    sink = CollectingEventSink()
    clerk = KernelRuntime(sink)
    assert clerk.serve(lines=["create EnglishAgent.md", "linope create another.txt", "exit"]) == 0
    assert (tmp_path / "EnglishAgent.md").is_file()
    assert (tmp_path / "another.txt").is_file()
    values = [
        event.data["value"]
        for event in sink.events
        if event.kind == "command.completed"
    ]
    assert {"path": str(tmp_path / "EnglishAgent.md")} in values
    assert {"path": str(tmp_path / "another.txt")} in values


def test_a_one_shot_start_still_waits(monkeypatch) -> None:
    waited: dict[str, bool] = {}

    def hold(service, *, ping: bool, once: bool) -> bool:
        del service, ping, once
        waited["yes"] = True
        return True

    monkeypatch.setattr("kernel.command.process.start.hold", hold)
    monkeypatch.setattr(
        "kernel.command.process.start.open_capability",
        lambda options: object(),
    )
    assert start_capability(["tools.read"]) == 0
    assert waited["yes"] is True


def test_ask_reaches_the_living_window(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    sink = CollectingEventSink()
    clerk = KernelRuntime(sink)
    assert (
        clerk.serve(
            lines=[
                "process start tools.read",
                "ask missing -- read this",
                "exit",
            ]
        )
        == 0
    )
    failures = [event for event in sink.events if event.kind == "command.failed"]
    assert failures
    assert "full pid" in failures[-1].data["error"]["message"]


def test_a_typed_line_and_exit_are_journaled(tmp_path: Path, monkeypatch) -> None:
    from kernel.trace.journal import Journal, journal_path

    monkeypatch.chdir(tmp_path)
    clerk = KernelRuntime(CollectingEventSink())
    assert clerk.serve(lines=["list", "exit"]) == 0
    rows = Journal(journal_path()).rows()
    assert [row["text"] for row in rows] == ["list", "exit"]
    assert all(row["kind"] == "line" for row in rows)
    assert all("pid" not in row for row in rows)


def test_an_unknown_line_uses_the_command_table() -> None:
    sink = CollectingEventSink()
    clerk = KernelRuntime(sink)
    assert clerk.serve(lines=["no such line", "exit"]) == 0
    failures = [event for event in sink.events if event.kind == "command.failed"]
    assert failures[-1].data["error"]["code"] == "UsageError"
