"""Run the kernel command line: ``python -m kernel.command``."""

from __future__ import annotations

import json
import sys
import threading

from kernel.command.events import (
    KernelEvent,
    bind_event_sink,
    reset_event_sink,
)
from kernel.command.dispatch import main


class JsonlSink:
    """Serialize backend facts at the process entry point."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seq = 0

    def emit(self, event: KernelEvent) -> None:
        self._seq += 1
        payload = event.to_payload()
        payload["seq"] = self._seq
        with self._lock:
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
            sys.stdout.flush()


def run(argv: list[str] | None = None) -> int:
    """Run a command with the JSONL host adapter installed."""

    token = bind_event_sink(JsonlSink())
    try:
        return main(argv)
    finally:
        reset_event_sink(token)


if __name__ == "__main__":
    raise SystemExit(run())
