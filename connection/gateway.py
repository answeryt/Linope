"""Expose structured frontend actions over JSONL without changing the kernel."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from connection.protocol.request import ActionRequest, ProtocolError, parse_request
from connection.semantic.action_compiler import compile_action
from connection.semantic.action_types import CompiledAction, EnvironmentDefaults
from connection.transport.event_stream import EventStream
from connection.transport.kernel_session import KernelSession


class GatewayCommandError(RuntimeError):
    """A kernel command returned a structured failure event."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ConnectionGateway:
    """Translate semantic actions and drive one existing kernel session."""

    def __init__(self, cwd: str | Path | None = None) -> None:
        self._session = KernelSession(cwd=cwd)
        self._events = EventStream(sys.stdout)
        self._environment = EnvironmentDefaults()

    def serve(self) -> int:
        """Read action requests until stdin or the kernel session closes."""

        try:
            for raw in sys.stdin:
                if not raw.strip():
                    continue
                should_leave = self._handle_line(raw)
                if should_leave:
                    break
        finally:
            self._session.close()
        return 0

    def _handle_line(self, raw: str) -> bool:
        try:
            request = parse_request(json.loads(raw))
        except json.JSONDecodeError as exc:
            self._events.emit(
                "protocol.error",
                {"message": f"Invalid JSON request: {exc.msg}"},
                request_id="connection",
            )
            return False
        except ProtocolError as exc:
            self._events.failed("connection", "connection", exc.code, str(exc), exc.details)
            return False

        self._events.accepted(request.request_id, request.action)
        try:
            compiled = compile_action(request, self._environment)
            result = self._run_action(request, compiled)
        except ProtocolError as exc:
            self._events.failed(
                request.request_id,
                request.action,
                exc.code,
                str(exc),
                exc.details,
            )
            return False
        except GatewayCommandError as exc:
            self._events.failed(
                request.request_id,
                request.action,
                exc.code,
                exc.message,
            )
            return False
        except (OSError, RuntimeError, EOFError) as exc:
            self._events.failed(
                request.request_id,
                request.action,
                type(exc).__name__,
                str(exc),
            )
            return False

        if compiled.environment_update is not None:
            self._environment = compiled.environment_update
        self._events.completed(request.request_id, request.action, result)
        return compiled.completion == "session"

    def _run_action(self, request: ActionRequest, compiled: CompiledAction) -> Any:
        """Run each compiled command and wait for its terminal event."""

        result: Any = None
        for index, command in enumerate(compiled.commands):
            self._session.send(command)
            completion = compiled.completion if index == len(compiled.commands) - 1 else "command"
            result = self._read_until_complete(request.request_id, completion)
        return result

    def _read_until_complete(self, request_id: str, completion: str) -> Any:
        """Relay kernel events until the current action has reached its boundary."""

        while True:
            event = self._session.read_event()
            self._events.relay_kernel(event, request_id)
            kind = event["kind"]
            data = event["data"]
            if kind == "command.failed":
                error = data.get("error")
                if isinstance(error, dict):
                    code = str(error.get("code") or "command_failed")
                    message = str(error.get("message") or "Kernel command failed")
                else:
                    code = "command_failed"
                    message = str(error or "Kernel command failed")
                raise GatewayCommandError(code, message)
            if kind == "session.closed":
                if completion == "session":
                    return None
                raise RuntimeError("kernel_session_closed")
            if completion == "command" and kind == "command.completed":
                return data.get("value")
            if completion == "turn" and kind in {"turn.completed", "command.completed"}:
                return data.get("result", data.get("value"))


def main() -> int:
    """Run the structured connection gateway from the repository root."""

    return ConnectionGateway(cwd=Path.cwd()).serve()


if __name__ == "__main__":
    raise SystemExit(main())
