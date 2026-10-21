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
    assert clerk.serve(lines=["create 英语Agent.md", "linope create 另一份.txt", "exit"]) == 0
    assert (tmp_path / "英语Agent.md").is_file()
    assert (tmp_path / "另一份.txt").is_file()
    output = capsys.readouterr().out
    assert "英语Agent.md" in output
    assert "另一份.txt" in output
    assert "load <种类>" not in output


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
                "ask missing -- 读一下",
                "exit",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "linope create" not in captured.err
    assert "完整进程号" in captured.err


def test_an_unknown_line_uses_the_command_table(capsys) -> None:
    clerk = Clerk()
    assert clerk.serve(lines=["没有这条", "exit"]) == 0
    captured = capsys.readouterr()
    assert "linope create" in captured.err
    assert "load <种类>" not in captured.err
    assert "load <种类>" not in captured.out
