"""Run the existing kernel command session behind the semantic gateway."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from connection.transport.jsonl import read_json_line


class KernelWireError(RuntimeError):
    """The kernel session emitted a malformed or undecodable JSONL event."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class KernelSession:
    """A blocking adapter for ``python -m kernel.command session``."""

    def __init__(self, cwd: str | Path | None = None) -> None:
        environment = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
        self._write_lock = threading.Lock()
        self._process = subprocess.Popen(
            [sys.executable, "-u", "-m", "kernel.command.server"],
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

    def send(self, command: str, request_id: str = "") -> None:
        """Send one command to the kernel server."""

        if self._process.poll() is not None:
            raise RuntimeError("kernel_session_closed")
        payload: dict[str, Any] = {"command": command.strip()}
        if request_id:
            payload["id"] = request_id
        with self._write_lock:
            self._stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._stdin.flush()

    def read_event(self) -> dict[str, Any]:
        """Read one validated kernel event from stdout."""

        try:
            value = read_json_line(self._stdout)
        except JSONDecodeError as exc:
            raise KernelWireError("invalid_json", str(exc)) from exc
        if not isinstance(value, dict):
            raise KernelWireError("kernel_event_not_object", "Kernel event must be an object")
        if value.get("version") != 1 or not isinstance(value.get("kind"), str):
            raise KernelWireError(
                "invalid_kernel_event",
                "Kernel event must include version 1 and a kind",
            )
        if not isinstance(value.get("data"), dict):
            raise KernelWireError(
                "invalid_kernel_event_data",
                "Kernel event data must be an object",
            )
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
