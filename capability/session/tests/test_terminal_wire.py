"""A bad server request stays on the versioned event wire."""

from __future__ import annotations

import json
from io import StringIO

import kernel.command.server as server


def test_server_error_is_a_versioned_kernel_event(monkeypatch) -> None:
    incoming = StringIO('{"command": ""}\n')
    outgoing = StringIO()
    monkeypatch.setattr(server.sys, "stdin", incoming)
    monkeypatch.setattr(server.sys, "stdout", outgoing)

    assert server.main() == 0

    events = [json.loads(line) for line in outgoing.getvalue().splitlines() if line.strip()]
    failed = next(event for event in events if event["kind"] == "command.failed")
    assert failed["version"] == 1
    assert failed["seq"] >= 1
    assert failed["data"]["error"]["message"] == "request must include command"
