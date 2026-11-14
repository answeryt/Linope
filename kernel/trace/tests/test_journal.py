"""The turn journal keeps every line it is given."""

import json
from pathlib import Path

import pytest

from kernel.command.log import run
from kernel.trace.journal import Journal, journal_path


def test_two_appends_come_back_in_order(tmp_path: Path) -> None:
    journal = Journal(tmp_path / "log" / "session.jsonl")
    journal.append({"kind": "line", "text": "list"})
    journal.append({"kind": "model", "pid": 7, "text": "original", "step": "read"})

    rows = journal.rows()
    assert [row["kind"] for row in rows] == ["line", "model"]
    assert rows[0]["text"] == "list"
    assert rows[1]["text"] == "original"
    assert rows[1]["pid"] == 7
    assert rows[0]["time"]
    again = journal.path.read_text(encoding="utf-8").splitlines()
    assert json.loads(again[0])["text"] == "list"
    assert json.loads(again[1])["step"] == "read"


def test_log_prints_every_line_and_one_process(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    journal = Journal(journal_path())
    journal.append({"kind": "line", "text": "list"})
    journal.append({"kind": "model", "pid": 7, "text": "A", "step": "answer"})
    journal.append({"kind": "model", "pid": 8, "text": "B", "step": "read"})

    everything = json.dumps(run([]), ensure_ascii=False)
    assert "list" in everything
    assert "A" in everything
    assert "B" in everything

    one = json.dumps(run(["7"]), ensure_ascii=False)
    assert "A" in one
    assert "B" not in one
    assert "list" not in one

    with pytest.raises(LookupError, match="9"):
        run(["9"])
    with pytest.raises(ValueError, match="number"):
        run(["nope"])


def test_log_without_a_file_says_so(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="No turn log yet"):
        run([])
