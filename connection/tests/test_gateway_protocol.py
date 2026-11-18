"""Protocol-level integration tests for the shared gateway."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_gateway_relays_a_real_kernel_session() -> None:
    root = Path(__file__).resolve().parents[2]
    request = {
        "version": 1,
        "request_id": "gateway-test",
        "action": "command.execute",
        "payload": {"command": "exit"},
    }
    completed = subprocess.run(
        [sys.executable, "-m", "connection.gateway"],
        input=json.dumps(request) + "\n",
        text=True,
        capture_output=True,
        cwd=root,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    assert events
    assert all(event["version"] == 1 for event in events)
    assert all(event["request_id"] in {"gateway-test", "connection"} for event in events)
    kinds = [event["kind"] for event in events]
    assert kinds[0] == "action.accepted"
    assert "session.started" in kinds
    assert "session.closed" in kinds
    assert kinds[-1] == "action.completed"
