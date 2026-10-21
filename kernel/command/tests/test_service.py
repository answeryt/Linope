"""service start records process ids and does not start them."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from kernel.command.service import run
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
        assert run(["start", str(first.pid), str(second.pid)]) == 0
        output = capsys.readouterr().out
        assert "service=1\n" in output
        assert f"pid={first.pid} capability=tools.read" in output
        assert f"pid={second.pid} capability=tools.glob" in output
        saved = ServiceBook(tmp_path / ".linope" / "services.json").groups()
        assert saved == (
            ServiceGroup(service_id=1, pids=(int(first.pid or 0), int(second.pid or 0))),
        )
        assert run(["start", str(first.pid)]) == 0
        again = ServiceBook(tmp_path / ".linope" / "services.json").groups()
        assert again[1] == ServiceGroup(service_id=2, pids=(int(first.pid or 0),))
    finally:
        _stop(first)
        _stop(second)


def test_a_missing_pid_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert run(["start", "424242"]) == 1
    assert "424242" in capsys.readouterr().err
    assert not (tmp_path / ".linope" / "services.json").exists()


def test_a_closed_pid_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    _save(tmp_path, [_ready(424242, "tools.read", status="closed")])
    assert run(["start", "424242"]) == 1
    assert not (tmp_path / ".linope" / "services.json").exists()


def test_a_dead_process_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    _save(tmp_path, [_ready(424242, "tools.read")])
    assert run(["start", "424242"]) == 1
    assert not (tmp_path / ".linope" / "services.json").exists()
    record = ProcessResourceBook(
        ProcessLedger(tmp_path / ".linope" / "processes.json")
    ).get(424242)
    assert record is not None
    assert record.status == RecordStatus.CLOSED


def test_one_bad_pid_does_not_keep_a_partial_service(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    living = _sleeper()
    try:
        _save(tmp_path, [_ready(int(living.pid or 0), "tools.read")])
        assert run(["start", str(living.pid), "424242"]) == 1
        assert not (tmp_path / ".linope" / "services.json").exists()
    finally:
        _stop(living)


def test_a_repeated_pid_writes_nothing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert run(["start", "5", "5"]) == 1
    assert "两遍" in capsys.readouterr().err
    assert not (tmp_path / ".linope" / "services.json").exists()
