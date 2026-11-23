"""Protocol-level integration tests for the shared gateway."""

from __future__ import annotations

import json
import os
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


def test_gateway_returns_model_catalog_without_starting_a_kernel_command() -> None:
    root = Path(__file__).resolve().parents[2]
    requests = [
        {
            "version": 1,
            "request_id": "catalog-test",
            "action": "model.catalog",
            "payload": {},
        },
        {
            "version": 1,
            "request_id": "stop",
            "action": "command.execute",
            "payload": {"command": "exit"},
        },
    ]
    completed = subprocess.run(
        [sys.executable, "-m", "connection.gateway"],
        input="".join(json.dumps(item) + "\n" for item in requests),
        text=True,
        capture_output=True,
        cwd=root,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    catalog_event = next(
        event
        for event in events
        if event["kind"] == "action.completed" and event["request_id"] == "catalog-test"
    )
    catalog = catalog_event["data"]["result"]
    assert any(item["capability"] == "model.openai_chat_model" for item in catalog)


def test_gateway_keeps_concurrent_actions_on_their_own_request_ids(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    requests = [
        {
            "version": 1,
            "request_id": "one",
            "action": "command.execute",
            "payload": {"command": "create one.txt"},
        },
        {
            "version": 1,
            "request_id": "two",
            "action": "command.execute",
            "payload": {"command": "create two.txt"},
        },
        {
            "version": 1,
            "request_id": "stop",
            "action": "command.execute",
            "payload": {"command": "exit"},
        },
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-m", "connection.gateway"],
        input="".join(json.dumps(item) + "\n" for item in requests),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        env=env,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    finished = [
        event["request_id"]
        for event in events
        if event["kind"] == "action.completed" and event["request_id"] in {"one", "two"}
    ]
    assert finished == ["one", "two"]
    assert (tmp_path / "one.txt").is_file()
    assert (tmp_path / "two.txt").is_file()
    for event in events:
        if event.get("request_id") != "one":
            continue
        command = event["data"].get("command")
        assert command in {None, "create one.txt"}


def test_gateway_emits_one_action_failure_for_a_kernel_command_failure() -> None:
    root = Path(__file__).resolve().parents[2]
    requests = [
        {
            "version": 1,
            "request_id": "failure-test",
            "action": "command.execute",
            "payload": {"command": "model run -- hello"},
        },
        {
            "version": 1,
            "request_id": "stop",
            "action": "command.execute",
            "payload": {"command": "exit"},
        },
    ]
    completed = subprocess.run(
        [sys.executable, "-m", "connection.gateway"],
        input="".join(json.dumps(item) + "\n" for item in requests),
        text=True,
        capture_output=True,
        cwd=root,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    events = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    failure_events = [
        event for event in events if event.get("request_id") == "failure-test"
    ]
    assert [event["kind"] for event in failure_events].count("command.failed") == 0
    failures = [event for event in failure_events if event["kind"] == "action.failed"]
    assert len(failures) == 1
    assert failures[0]["data"]["error"]["message"] == "model_not_configured"
