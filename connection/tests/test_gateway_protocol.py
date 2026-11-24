"""Protocol-level integration tests for the shared gateway."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
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


def test_gateway_calls_list_dir_and_returns_the_plugin_result(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    (tmp_path / "notes.txt").write_text("alpha\n", encoding="utf-8")
    requests = [
        {
            "version": 1,
            "request_id": "listed",
            "action": "capability.call",
            "payload": {
                "capability": "tools.list_dir",
                "kind": "tool",
                "hold": False,
                "cwd": str(tmp_path),
                "body": {"path": str(tmp_path)},
            },
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
    # Keep the session open until the two-step call finishes. Closing stdin
    # or sending exit early drops the process before the load is sent.
    gateway = subprocess.Popen(
        [sys.executable, "-m", "connection.gateway"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=root,
        env=env,
    )
    assert gateway.stdin is not None
    assert gateway.stdout is not None
    gateway.stdin.write(json.dumps(requests[0]) + "\n")
    gateway.stdin.flush()
    events = []
    deadline = time.time() + 60
    while time.time() < deadline:
        line = gateway.stdout.readline()
        if not line:
            break
        events.append(json.loads(line))
        if any(event["kind"] in {"action.completed", "action.failed"} and event.get("request_id") == "listed" for event in events):
            break
    gateway.stdin.write(json.dumps(requests[1]) + "\n")
    gateway.stdin.close()
    stderr = gateway.stderr.read() if gateway.stderr is not None else ""
    assert gateway.wait(timeout=20) == 0, stderr
    finished = next(event for event in events if event["kind"] == "action.completed" and event["request_id"] == "listed")
    result = finished["data"]["result"]
    payload = json.loads(result) if isinstance(result, str) else result
    names = [item["name"] for item in payload["entries"]]
    assert "notes.txt" in names


def test_gateway_runs_a_short_python_program() -> None:
    root = Path(__file__).resolve().parents[2]
    request = {
        "version": 1,
        "request_id": "ran",
        "action": "capability.call",
        "payload": {
            "capability": "tools.run_code",
            "kind": "tool",
            "hold": False,
            "body": {"code": "return 1 + 1", "description": "return 1 + 1"},
        },
    }
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    gateway = subprocess.Popen(
        [sys.executable, "-m", "connection.gateway"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=root,
        env=env,
    )
    assert gateway.stdin is not None and gateway.stdout is not None
    gateway.stdin.write(json.dumps(request) + "\n")
    gateway.stdin.flush()
    events = []
    deadline = time.time() + 60
    while time.time() < deadline:
        line = gateway.stdout.readline()
        if not line:
            break
        events.append(json.loads(line))
        if any(event.get("request_id") == "ran" and event["kind"] in {"action.completed", "action.failed"} for event in events):
            break
    gateway.stdin.write(json.dumps({"version": 1, "request_id": "stop", "action": "command.execute", "payload": {"command": "exit"}}) + "\n")
    gateway.stdin.close()
    stderr = gateway.stderr.read() if gateway.stderr is not None else ""
    assert gateway.wait(timeout=20) == 0, stderr
    finished = next(event for event in events if event["kind"] == "action.completed" and event["request_id"] == "ran")
    result = finished["data"]["result"]
    payload = json.loads(result) if isinstance(result, str) else result
    assert payload["success"] is True
    assert payload["result"] == 2


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
