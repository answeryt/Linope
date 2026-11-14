"""External interactive session capability.

The session owns the user's terminal.  Kernel state is reached through the
JSONL server rather than by importing the kernel command loop.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any


def main() -> int:
    server = subprocess.Popen(
        [sys.executable, "-m", "kernel.command.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=None,
    )
    assert server.stdin is not None
    assert server.stdout is not None
    try:
        for raw in sys.stdin:
            command = raw.strip()
            if not command:
                continue
            server.stdin.write(json.dumps({"command": command}, ensure_ascii=False) + "\n")
            server.stdin.flush()
            leaving = _read_reply(server.stdout)
            if leaving:
                break
    finally:
        try:
            server.stdin.close()
        except OSError:
            pass
        server.wait()
    return int(server.returncode or 0)


def _read_reply(stream: Any) -> bool:
    while True:
        raw = stream.readline()
        if not raw:
            return True
        payload = json.loads(raw)
        event = payload.get("event")
        if event == "kernel":
            _write(payload.get("payload") or {})
            continue
        if event == "error":
            _write(
                {
                    "kind": "command.failed",
                    "data": dict(payload.get("error") or {}),
                }
            )
            return False
        if event == "done":
            return bool(payload.get("leaving"))


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    raise SystemExit(main())
