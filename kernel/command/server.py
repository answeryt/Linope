"""JSONL IPC host for an external session capability.

The session process owns stdin/stdout.  This server owns the kernel command
state and exposes one request at a time over pipes.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from kernel.command.events import KernelEvent
from kernel.command.runtime import KernelRuntime


class _Sink:
    def __init__(self) -> None:
        self.events: list[KernelEvent] = []

    def emit(self, event: KernelEvent) -> None:
        self.events.append(event)


def main() -> int:
    sink = _Sink()
    runtime = KernelRuntime(sink)
    runtime.emit("session.started", {"cwd": str(Path.cwd())})
    _write({"event": "kernel", "payload": sink.events[-1].to_payload()})
    sink.events.clear()
    try:
        for raw in sys.stdin:
            try:
                request = json.loads(raw)
                if not isinstance(request, dict):
                    raise ValueError("request must be an object")
                command = str(request.get("command") or "").strip()
                if not command:
                    raise ValueError("request must include command")
                sink.events.clear()
                leaving = runtime.command(command)
                while runtime.drive.busy():
                    runtime.drive.step()
                    time.sleep(0.01)
                for event in sink.events:
                    _write({"event": "kernel", "payload": event.to_payload()})
                if leaving:
                    previous = len(sink.events)
                    runtime.close()
                    runtime.emit("session.closed", {})
                    for event in sink.events[previous:]:
                        _write({"event": "kernel", "payload": event.to_payload()})
                _write({"event": "done", "leaving": leaving})
                if leaving:
                    break
            except Exception as exc:
                _write(
                    {
                        "event": "error",
                        "error": {"code": type(exc).__name__, "message": str(exc)},
                    }
                )
    finally:
        runtime.close()
    return 0


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
