"""Capability notices stay framed on the internal RPC stream."""

from __future__ import annotations

import json
from io import StringIO
from kernel.process.process_manager.capability_process import _reply_line
from kernel.process.process_runtime.runtime import _serve_steps


class _Adapter:
    def handle(self, payload):
        from kernel.process.process_runtime.runtime import emit_notice

        emit_notice({"kind": "model.delta", "text": "hi"})
        return {"ok": payload.get("body")}


def test_runtime_frames_notice_before_final_result() -> None:
    incoming = StringIO(json.dumps({"operation": "load", "body": "hello"}) + "\n")
    outgoing = StringIO()
    _serve_steps(
        incoming,
        outgoing,
        _Adapter(),
        {"thread_id": "7"},
        7,
    )
    rows = [json.loads(line) for line in outgoing.getvalue().splitlines()]
    assert rows[0] == {
        "event": "notice",
        "notice": {"kind": "model.delta", "text": "hi"},
        "pid": 7,
        "thread": "7",
        "turn_id": "",
    }
    assert rows[1]["event"] == "result"
    assert rows[1]["result"] == {"ok": "hello"}


def test_parent_delivers_notice_to_the_active_exchange() -> None:
    seen: list[dict] = []
    reply = _reply_line(
        {"operation": "load"},
        {
            "event": "notice",
            "notice": {"kind": "model.delta", "text": "hi"},
            "pid": 7,
            "turn_id": "1.1",
        },
        seen.append,
    )
    assert reply is None
    assert seen == [{"kind": "model.delta", "text": "hi", "pid": 7, "turn_id": "1.1"}]
