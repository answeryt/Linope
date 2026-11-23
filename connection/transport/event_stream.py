"""Normalize kernel events into the versioned frontend event stream."""

from __future__ import annotations

import threading
from typing import Any, TextIO

from connection.transport.jsonl import write_json_line


class EventStream:
    """Write connection events with gateway-owned sequence numbers."""

    def __init__(self, output: TextIO) -> None:
        self._output = output
        self._sequence = 0
        self._lock = threading.Lock()

    def emit(
        self,
        kind: str,
        data: dict[str, Any],
        *,
        request_id: str | None = None,
        turn_id: str | None = None,
        pid: int | None = None,
    ) -> dict[str, Any]:
        """Write one normalized event and return its payload."""

        with self._lock:
            self._sequence += 1
            event: dict[str, Any] = {
                "version": 1,
                "kind": kind,
                "seq": self._sequence,
                "data": data,
            }
            if request_id is not None:
                event["request_id"] = request_id
            if turn_id is not None:
                event["turn_id"] = turn_id
            if pid is not None:
                event["pid"] = pid
            write_json_line(self._output, event)
            return event

    def relay_kernel(self, event: dict[str, Any], request_id: str) -> dict[str, Any]:
        """Forward one kernel event while correlating it to the action."""

        data = dict(event["data"])
        kernel_request_id = event.get("request_id")
        if isinstance(kernel_request_id, str) and kernel_request_id != request_id:
            data["_kernel_request_id"] = kernel_request_id
        return self.emit(
            str(event["kind"]),
            data,
            request_id=request_id,
            turn_id=event.get("turn_id") if isinstance(event.get("turn_id"), str) else None,
            pid=event.get("pid") if isinstance(event.get("pid"), int) else None,
        )

    def accepted(self, request_id: str, action: str) -> dict[str, Any]:
        """Emit an action accepted event."""

        return self.emit("action.accepted", {"action": action}, request_id=request_id)

    def completed(self, request_id: str, action: str, result: Any = None) -> dict[str, Any]:
        """Emit an action completed event."""

        data: dict[str, Any] = {"action": action}
        if result is not None:
            data["result"] = result
        return self.emit("action.completed", data, request_id=request_id)

    def failed(
        self,
        request_id: str,
        action: str,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Emit a structured action failure."""

        error: dict[str, Any] = {"code": code, "message": message}
        if details:
            error["details"] = details
        return self.emit(
            "action.failed",
            {"action": action, "error": error},
            request_id=request_id,
        )
