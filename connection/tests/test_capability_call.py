"""Desktop capability.call stays on the allowlist."""

from __future__ import annotations

import json

import pytest

from connection.protocol.request import ProtocolError, parse_request
from connection.semantic.capability_call import (
    load_command,
    prepare_capability_call,
    start_command,
)


def test_unlisted_capability_is_rejected() -> None:
    request = parse_request(
        {
            "version": 1,
            "request_id": "call-1",
            "action": "capability.call",
            "payload": {
                "capability": "tools.pwsh",
                "kind": "tool",
                "body": {"command": "Get-Location"},
            },
        }
    )
    with pytest.raises(ProtocolError, match="Unsupported capability"):
        prepare_capability_call(request.payload)


def test_sandbox_kind_must_match_the_capability() -> None:
    with pytest.raises(ProtocolError, match="uses kind sandbox"):
        prepare_capability_call(
            {
                "capability": "sandbox.sandbox",
                "kind": "tool",
                "body": {"mode": "read-only"},
            }
        )


def test_held_list_dir_start_omits_once_and_load_keeps_the_body() -> None:
    spec = prepare_capability_call(
        {
            "capability": "tools.list_dir",
            "kind": "tool",
            "hold": True,
            "cwd": r"C:\work",
            "body": {"path": r"C:\work"},
        }
    )
    assert start_command(spec).split()[:3] == ["process", "start", "tools.list_dir"]
    assert "--once" not in start_command(spec)
    command = load_command(spec, 12)
    head, body = command.split(" -- ", 1)
    assert head == "load tool 12"
    assert json.loads(body) == {"path": r"C:\work"}


def test_one_shot_call_closes_after_the_load() -> None:
    spec = prepare_capability_call(
        {"capability": "tools.read", "kind": "tool", "body": {"file_path": "note.txt"}}
    )
    assert start_command(spec).endswith("--once")
