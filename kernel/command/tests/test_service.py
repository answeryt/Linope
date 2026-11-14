"""service start records process ids; service load hands a line to the entry process."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from kernel.command.parser import UsageError
from kernel.command.service import accept, entry_of, run
from kernel.process.ledger import ProcessLedger
from kernel.process.resource_record import ProcessResourceBook, RecordStatus
from kernel.services.collection import ServiceBook, ServiceGroup


def _ready(pid: int, capability: str, *, status: str = "ready") -> dict:
    return {
        "capability_id": capability,
        "status": status,
        "claims": [],
        "leases": [],
        "room": {},
        "pid": pid,
        "started": "",
    }


def _save(tmp_path: Path, records: list[dict]) -> None:
    ProcessLedger(tmp_path / ".linope" / "processes.json").write(records)


def _sleeper() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _stop(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.kill()
        process.wait(timeout=5)


def test_two_living_pids_become_one_service(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    first = _sleeper()
    second = _sleeper()
    try:
        _save(
            tmp_path,
            [
                _ready(int(first.pid or 0), "tools.read"),
                _ready(int(second.pid or 0), "tools.glob"),
            ],
        )
        started = run(["start", str(first.pid), str(second.pid)])
        assert started["service_id"] == 1
        assert {item["capability"] for item in started["processes"]} == {
            "tools.read",
            "tools.glob",
        }
        saved = ServiceBook(tmp_path / ".linope" / "services.json").groups()
        assert saved == (
            ServiceGroup(service_id=1, pids=(int(first.pid or 0), int(second.pid or 0))),
        )
        assert run(["start", str(first.pid)])["service_id"] == 2
        again = ServiceBook(tmp_path / ".linope" / "services.json").groups()
        assert again[1] == ServiceGroup(service_id=2, pids=(int(first.pid or 0),))
    finally:
        _stop(first)
        _stop(second)


def test_a_missing_pid_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="424242"):
        run(["start", "424242"])
    assert not (tmp_path / ".linope" / "services.json").exists()


def test_a_closed_pid_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _save(tmp_path, [_ready(424242, "tools.read", status="closed")])
    with pytest.raises(ValueError, match="424242"):
        run(["start", "424242"])
    assert not (tmp_path / ".linope" / "services.json").exists()


def test_a_dead_process_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _save(tmp_path, [_ready(424242, "tools.read")])
    with pytest.raises(ValueError, match="424242"):
        run(["start", "424242"])
    assert not (tmp_path / ".linope" / "services.json").exists()
    record = ProcessResourceBook(
        ProcessLedger(tmp_path / ".linope" / "processes.json")
    ).get(424242)
    assert record is not None
    assert record.status == RecordStatus.CLOSED


def test_one_bad_pid_does_not_keep_a_partial_service(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    living = _sleeper()
    try:
        _save(tmp_path, [_ready(int(living.pid or 0), "tools.read")])
        with pytest.raises(ValueError, match="424242"):
            run(["start", str(living.pid), "424242"])
        assert not (tmp_path / ".linope" / "services.json").exists()
    finally:
        _stop(living)


def test_a_repeated_pid_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="twice"):
        run(["start", "5", "5"])
    assert not (tmp_path / ".linope" / "services.json").exists()


class _Process:
    def __init__(self, pid: int, capability: str, *, alive: bool = True) -> None:
        self.pid = pid
        self.capability = capability
        self.is_alive = alive
        self.activation = type("Activation", (), {
            "pid": pid,
            "settings": {"slot": "model"} if str(capability).startswith("model.") else {},
        })()


class _Window:
    def __init__(self, *processes: _Process) -> None:
        self._items = processes
        self.closed: list[str] = []

    def processes(self) -> tuple[_Process, ...]:
        return self._items

    def close_once(self, text: str) -> None:
        self.closed.append(text)


def _book(tmp_path: Path, *groups: tuple[int, ...]) -> ServiceBook:
    book = ServiceBook(tmp_path / ".linope" / "services.json")
    for pids in groups:
        book.add(pids)
    return book


def test_get_finds_a_service_by_its_number(tmp_path: Path) -> None:
    book = _book(tmp_path, (11, 12), (13,))
    assert book.get(2) == ServiceGroup(service_id=2, pids=(13,))
    assert book.get(3) is None


def test_the_first_living_process_is_the_entry() -> None:
    group = ServiceGroup(service_id=1, pids=(12, 11))
    processes = (_Process(12, "tools.ddgs"), _Process(11, "tools.read"))
    assert entry_of(group, processes) == 11


def test_living_process_is_still_an_entry() -> None:
    group = ServiceGroup(service_id=1, pids=(11, 12))
    processes = (
        _Process(11, "tools.read", alive=False),
        _Process(12, "tools.ddgs"),
    )
    assert entry_of(group, processes) == 12


def test_multiple_processes_use_the_lowest_member() -> None:
    group = ServiceGroup(service_id=1, pids=(11, 12))
    processes = (_Process(11, "tools.read"), _Process(12, "tools.write"))
    assert entry_of(group, processes) == 11


def test_membership_controls_the_entry() -> None:
    group = ServiceGroup(service_id=1, pids=(12,))
    processes = (_Process(11, "tools.read"), _Process(12, "tools.ddgs"))
    assert entry_of(group, processes) == 12


def _speak(monkeypatch, window: Any, line: str) -> tuple[int, list[str]]:
    import kernel.command.process.listen as listen

    handed: list[str] = []

    def one_line(_window: Any, raw: str, timeout: float, *, emit_done: bool = True) -> bool:
        handed.append(raw)
        return True

    monkeypatch.setattr(listen, "_one_line", one_line)
    code = run(
        line.split(" -- ", 1)[0].split()[1:],
        runtime=window,
        request={"line": line},
    )
    return code, handed


def test_service_load_hands_the_entry_the_same_load_message_line(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _book(tmp_path, (21, 22))
    window = _Window(_Process(21, "tools.ddgs"), _Process(22, "tools.read"))
    code, handed = _speak(monkeypatch, window, "service load 1 -- today -- city weather")
    assert code == 0
    assert handed == ["load message 21 -- today -- city weather"]
    assert window.closed == handed


def test_service_load_with_a_word_for_a_number_sends_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _book(tmp_path, (22,))
    window = _Window(_Process(22, "tools.read"))
    with pytest.raises(UsageError, match="service load"):
        _speak(monkeypatch, window, "service load abc -- hello")


def test_service_load_of_a_missing_service_sends_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    window = _Window(_Process(22, "tools.read"))
    with pytest.raises(ValueError, match="No such service: 7"):
        _speak(monkeypatch, window, "service load 7 -- hello")


def test_arrived_words_go_to_the_entry_as_load_message(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _book(tmp_path, (21, 22))
    window = _Window(_Process(21, "tools.ddgs"), _Process(22, "tools.read"))
    handed: list[str] = []

    def one_line(_window: Any, raw: str, timeout: float, *, emit_done: bool = True) -> bool:
        handed.append(raw)
        return True

    monkeypatch.setattr("kernel.command.process.listen._one_line", one_line)
    line = accept(window, 1, "today -- city weather")
    assert line == "load message 21 -- today -- city weather"
    assert handed == [line]
    assert "channel" not in accept.__code__.co_varnames


def test_arrived_words_for_a_missing_service_are_not_handed(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    window = _Window(_Process(22, "tools.read"))
    handed: list[str] = []
    monkeypatch.setattr(
        "kernel.command.process.listen._one_line",
        lambda *_args, **_kwargs: handed.append("called"),
    )
    with pytest.raises(ValueError, match="No such service: 7"):
        accept(window, 7, "hello")
    assert handed == []


def test_service_load_without_a_window_sends_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _book(tmp_path, (22,))
    with pytest.raises(UsageError, match="service load"):
        _speak(monkeypatch, None, "service load 1 -- hello")
