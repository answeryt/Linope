"""Expose structured frontend actions over JSONL without changing the kernel."""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from connection.protocol.request import ActionRequest, ProtocolError, parse_request
from connection.semantic.action_compiler import compile_action
from connection.semantic.action_types import EnvironmentDefaults
from connection.semantic.model_catalog import discover_model_cards
from connection.transport.event_stream import EventStream
from connection.transport.kernel_session import KernelSession, KernelWireError


class GatewayCommandError(RuntimeError):
    """A kernel command returned a structured failure event."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class _Pending:
    """One action waiting on the kernel."""

    request: ActionRequest
    commands: tuple[str, ...]
    index: int = 0
    completion: str = "command"
    environment_update: EnvironmentDefaults | None = None
    phase: str = "command"
    result: Any = None


@dataclass
class ConnectionGateway:
    """Translate semantic actions and drive one existing kernel session."""

    cwd: str | Path | None = None
    _session: KernelSession = field(init=False)
    _events: EventStream = field(init=False)
    _environment: EnvironmentDefaults = field(default_factory=EnvironmentDefaults)
    _pending: dict[str, _Pending] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _reader: threading.Thread | None = field(default=None)
    _closed: bool = False

    def __post_init__(self) -> None:
        self._session = KernelSession(cwd=self.cwd)
        self._events = EventStream(sys.stdout)

    def serve(self) -> int:
        """Read action requests until stdin closes or the kernel session ends."""

        try:
            for raw in sys.stdin:
                if not raw.strip():
                    continue
                if self._closed:
                    break
                self._handle_line(raw)
        finally:
            self._session.close()
            reader = self._reader
            if reader is not None:
                reader.join(timeout=5)
        return 0

    def _handle_line(self, raw: str) -> None:
        try:
            request = parse_request(json.loads(raw))
        except json.JSONDecodeError as exc:
            self._events.emit(
                "protocol.error",
                {"message": f"Invalid JSON request: {exc.msg}"},
                request_id="connection",
            )
            return
        except ProtocolError as exc:
            self._events.failed("connection", "connection", exc.code, str(exc), exc.details)
            return

        self._events.accepted(request.request_id, request.action)
        if request.action == "model.catalog":
            self._events.completed(
                request.request_id,
                request.action,
                discover_model_cards(Path.cwd()),
            )
            return
        try:
            with self._lock:
                defaults = self._environment
            compiled = compile_action(request, defaults)
        except ProtocolError as exc:
            self._events.failed(
                request.request_id,
                request.action,
                exc.code,
                str(exc),
                exc.details,
            )
            return

        pending = _Pending(
            request=request,
            commands=compiled.commands,
            completion=compiled.completion,
            environment_update=compiled.environment_update,
        )
        with self._lock:
            self._pending[request.request_id] = pending
        self._ensure_reader()
        try:
            self._session.send(pending.commands[0], request.request_id)
        except (OSError, RuntimeError, EOFError) as exc:
            self._fail(request.request_id, type(exc).__name__, str(exc))

    def _ensure_reader(self) -> None:
        if self._reader is not None:
            return
        reader = threading.Thread(target=self._read_loop, name="linope-gateway", daemon=True)
        self._reader = reader
        reader.start()

    def _read_loop(self) -> None:
        while not self._closed:
            try:
                event = self._session.read_event()
            except EOFError:
                self._on_session_closed()
                return
            except KernelWireError as exc:
                self._fail_open(exc.code, exc.message)
                return
            except (OSError, RuntimeError) as exc:
                self._fail_open(type(exc).__name__, str(exc))
                return
            self._on_kernel(event)

    def _on_kernel(self, event: dict[str, Any]) -> None:
        kind = str(event.get("kind") or "")
        data = event.get("data")
        if not isinstance(data, dict):
            data = {}
        request_id = event.get("request_id")
        owner = request_id if isinstance(request_id, str) and request_id else ""

        if kind == "command.failed":
            code, message = _failure(data)
            self._fail(owner, code, message)
            return

        self._relay(event, owner or "connection")

        if kind == "session.closed":
            self._on_session_closed()
            return

        with self._lock:
            pending = self._pending.get(owner)
        if pending is None:
            return

        if kind == "command.accepted" and data.get("deferred") is True:
            with self._lock:
                current = self._pending.get(owner)
                if current is not None:
                    current.phase = "turn"
            return

        if kind == "command.completed":
            self._advance(owner, data.get("value"))
            return

        if kind == "turn.completed" and pending.phase == "turn":
            self._finish(owner, data.get("result", data.get("value")))

    def _advance(self, request_id: str, value: Any) -> None:
        with self._lock:
            pending = self._pending.get(request_id)
            if pending is None:
                return
            pending.result = value
            pending.index += 1
            if pending.index < len(pending.commands):
                command = pending.commands[pending.index]
            else:
                command = ""
                done = pending.phase != "turn"
            if command:
                done = False
        if command:
            try:
                self._session.send(command, request_id)
            except (OSError, RuntimeError, EOFError) as exc:
                self._fail(request_id, type(exc).__name__, str(exc))
            return
        if done:
            self._finish(request_id, value)

    def _finish(self, request_id: str, result: Any) -> None:
        with self._lock:
            pending = self._pending.pop(request_id, None)
        if pending is None:
            return
        if pending.environment_update is not None:
            with self._lock:
                self._environment = pending.environment_update
        self._events.completed(request_id, pending.request.action, result)

    def _fail(self, request_id: str, code: str, message: str) -> None:
        owner = request_id or "connection"
        with self._lock:
            pending = self._pending.pop(owner, None)
        action = pending.request.action if pending is not None else owner
        self._events.failed(owner, action, code, message)

    def _fail_open(self, code: str, message: str) -> None:
        with self._lock:
            owners = list(self._pending)
        for owner in owners:
            self._fail(owner, code, message)
        if not owners:
            self._events.failed("connection", "connection", code, message)
        self._closed = True

    def _on_session_closed(self) -> None:
        with self._lock:
            owners = list(self._pending)
        for owner in owners:
            pending = self._pending.get(owner)
            if pending is not None and pending.completion == "session":
                self._finish(owner, None)
            else:
                self._fail(owner, "kernel_session_closed", "kernel_session_closed")
        self._closed = True

    def _relay(self, event: dict[str, Any], request_id: str) -> None:
        self._events.relay_kernel(event, request_id)


def _failure(data: dict[str, Any]) -> tuple[str, str]:
    error = data.get("error")
    if isinstance(error, dict):
        return str(error.get("code") or "command_failed"), str(error.get("message") or "Kernel command failed")
    return "command_failed", str(error or "Kernel command failed")


def main() -> int:
    """Run the structured connection gateway from the repository root."""

    return ConnectionGateway(cwd=Path.cwd()).serve()


if __name__ == "__main__":
    raise SystemExit(main())
