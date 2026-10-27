"""One clerk can start more than one capability and still take the next line."""

from pathlib import Path

from kernel.command.process.clerk import Clerk
from kernel.command.process.start import run as start_capability


def test_two_starts_return_before_the_window_closes(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clerk = Clerk()
    assert (
        clerk.serve(
            lines=[
                "process start tools.read",
                "list",
                "process start tools.glob",
                "list",
                "exit",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert output.count("pid=") >= 4
    assert "process_id=" not in output
    assert output.count('{"type": "done"}') >= 4
    assert "tools.read" in output
    assert "tools.glob" in output


def test_create_writes_a_file_without_leaving_the_window(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clerk = Clerk()
    assert clerk.serve(lines=["create EnglishAgent.md", "linope create another.txt", "exit"]) == 0
    assert (tmp_path / "EnglishAgent.md").is_file()
    assert (tmp_path / "another.txt").is_file()
    output = capsys.readouterr().out
    assert "EnglishAgent.md" in output
    assert "another.txt" in output
    assert "load <kind>" not in output


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


def test_ask_reaches_the_living_window(tmp_path: Path, capsys, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    clerk = Clerk()
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
    captured = capsys.readouterr()
    assert "linope create" not in captured.err
    assert "full pid" in captured.err


def test_a_typed_line_and_exit_are_journaled(tmp_path: Path, monkeypatch, capsys) -> None:
    from kernel.trace.journal import Journal, journal_path

    monkeypatch.chdir(tmp_path)
    clerk = Clerk()
    assert clerk.serve(lines=["list", "exit"]) == 0
    capsys.readouterr()
    rows = Journal(journal_path()).rows()
    assert [row["text"] for row in rows] == ["list", "exit"]
    assert all(row["kind"] == "line" for row in rows)
    assert all("pid" not in row for row in rows)


def test_an_unknown_line_uses_the_command_table(capsys) -> None:
    clerk = Clerk()
    assert clerk.serve(lines=["no such line", "exit"]) == 0
    captured = capsys.readouterr()
    assert "linope create" in captured.err
    assert "load <kind>" not in captured.err
    assert "load <kind>" not in captured.out
