"""JSONL IPC host for an external session capability.

The session process owns stdin/stdout. This server runs the kernel command
loop and writes each versioned event as it happens. A command returns as soon
as the kernel has accepted it, including when a turn is still running.
"""

from __future__ import annotations

import json
import sys
import threading
from typing import Any

from kernel.command.events import KernelEvent, bind_event_sink, reset_event_sink
from kernel.command.process.clerk import CommandLine, KernelRuntime


class _Sink:
    """Write one event line immediately. Sequence numbers belong to this sink."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seq = 0

    def emit(self, event: KernelEvent) -> None:
        with self._lock:
            self._seq += 1
            payload = event.to_payload()
            payload["seq"] = self._seq
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def main() -> int:
    sink = _Sink()
    token = bind_event_sink(sink)
    runtime = KernelRuntime(sink)
    try:
        return runtime.serve(_commands(sys.stdin, runtime))
    finally:
        reset_event_sink(token)


def _commands(stream: Any, runtime: KernelRuntime) -> Any:
    """Yield parsed commands. A bad line becomes a failure event and is skipped."""

    for raw in stream:
        text = str(raw).strip()
        if not text:
            continue
        try:
            request = json.loads(text)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            command = str(request.get("command") or "").strip()
            if not command:
                raise ValueError("request must include command")
            request_id = request.get("id", "")
            if not isinstance(request_id, str):
                raise ValueError("request id must be a string")
        except Exception as exc:
            runtime.emit(
                "command.failed",
                {
                    "command": text,
                    "error": {"code": type(exc).__name__, "message": str(exc)},
                },
            )
            continue
        yield CommandLine(text=command, request_id=request_id.strip())


if __name__ == "__main__":
    raise SystemExit(main())
