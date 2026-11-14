"""The session process speaks only versioned JSONL facts."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_a_real_session_emits_only_structured_events(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "kernel.command", "session"],
        input="list\ncreate note.txt\nexit\n",
        text=True,
        capture_output=True,
        cwd=tmp_path,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert lines
    events = [json.loads(line) for line in lines]
    assert all(event["version"] == 1 and event["kind"] and event["seq"] for event in events)
    kinds = [event["kind"] for event in events]
    assert kinds[0] == "session.started"
    assert "session.closed" in kinds
    assert "command.completed" in kinds
    assert (tmp_path / "note.txt").is_file()
    assert "text-delta" not in completed.stderr
    assert "pid=" not in completed.stdout
    joined = "\n".join(lines)
    assert '{"type": "done"}' not in joined
    assert '{"type": "model"}' not in joined
