"""Run the existing kernel command session behind the semantic gateway."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from connection.transport.jsonl import read_json_line


class KernelSession:
    """A blocking adapter for ``python -m kernel.command session``."""

    def __init__(self, cwd: str | Path | None = None) -> None:
        environment = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
        self._process = subprocess.Popen(
            [sys.executable, "-u", "-m", "kernel.command", "session"],
            cwd=str(cwd) if cwd is not None else None,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
        )
        assert self._process.stdin is not None
        assert self._process.stdout is not None
        self._stdin = self._process.stdin
        self._stdout = self._process.stdout

    def send(self, command: str) -> None:
        """Send one raw command line to the existing kernel session."""

        if self._process.poll() is not None:
            raise RuntimeError("kernel_session_closed")
        self._stdin.write(command.strip() + "\n")
        self._stdin.flush()

    def read_event(self) -> dict[str, Any]:
        """Read one validated kernel event from stdout."""

        value = read_json_line(self._stdout)
        if not isinstance(value, dict):
            raise RuntimeError("kernel_event_not_object")
        if value.get("version") != 1 or not isinstance(value.get("kind"), str):
            raise RuntimeError("invalid_kernel_event")
        if not isinstance(value.get("data"), dict):
            raise RuntimeError("invalid_kernel_event_data")
        return value

    def close(self) -> None:
        """Ask the session to exit and release its pipes."""

        if self._process.poll() is None:
            try:
                self.send("exit")
            except (OSError, RuntimeError):
                self._process.kill()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
        self._stdin.close()
        self._stdout.close()
