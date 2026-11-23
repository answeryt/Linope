"""External interactive session capability.

The session owns the user's terminal. Kernel state is reached through the
JSONL server rather than by importing the kernel command loop.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading


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

    def forward_input() -> None:
        try:
            for raw in sys.stdin:
                command = raw.strip()
                if not command:
                    continue
                server.stdin.write(
                    json.dumps({"command": command}, ensure_ascii=False) + "\n"
                )
                server.stdin.flush()
        except (OSError, ValueError):
            pass
        finally:
            try:
                server.stdin.close()
            except OSError:
                pass

    threading.Thread(target=forward_input, name="linope-session-in", daemon=True).start()
    try:
        while True:
            line = server.stdout.readline()
            if not line:
                break
            sys.stdout.write(line)
            sys.stdout.flush()
    finally:
        server.wait()
    return int(server.returncode or 0)


if __name__ == "__main__":
    raise SystemExit(main())
