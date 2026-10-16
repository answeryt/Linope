"""Append-only text deltas shared by a capability process and the terminal.

The model process and the terminal session are peers. A stream file next to
the project is only a transient display channel: it is not a parent-child pipe
and it is not part of the portable project configuration.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from contextvars import ContextVar
from pathlib import Path
from typing import Any

_keys: ContextVar[tuple[str, ...]] = ContextVar("linope_stream_keys", default=())
_emitter: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar(
    "linope_live_emitter",
    default=None,
)


def stream_path(key: str) -> Path:
    """Return the transient file for one task or request."""
    from kernel.resource.store.locator import project_root

    safe = "".join(char if char.isalnum() else "_" for char in key)[:80] or "stream"
    return project_root() / ".linope" / "streams" / f"{safe}.jsonl"


def bind_stream_keys(keys: tuple[str, ...]):
    """Publish later text to these task and request names."""
    chosen = tuple(dict.fromkeys(str(key) for key in keys if str(key).strip()))
    return _keys.set(chosen)


def reset_stream_keys(token) -> None:
    _keys.reset(token)


def use_emitter(emitter: Callable[[dict[str, Any]], None] | None):
    """Route live events to one terminal session while a command is running."""
    return _emitter.set(emitter)


def reset_emitter(token) -> None:
    _emitter.reset(token)


def publish_text(text: str) -> None:
    if text:
        publish_event_to_bound({"type": "text-delta", "text": text})


def publish_status(text: str) -> None:
    if text:
        publish_event_to_bound({"type": "status", "text": text})


def publish_event(key: str, event: dict[str, Any]) -> None:
    """Append one event for a known task id."""
    if not key:
        return
    _append(stream_path(key), event)


def publish_event_to_bound(event: dict[str, Any]) -> None:
    for key in _keys.get():
        _append(stream_path(key), event)


def emit_live(event: dict[str, Any]) -> None:
    """Deliver one event to the active terminal, or to this process's output."""
    emitter = _emitter.get()
    if emitter is not None:
        emitter(event)
        return
    if event.get("type") == "text-delta":
        import sys

        sys.stdout.write(str(event.get("text") or ""))
        sys.stdout.flush()


def stream_keys_for(message: dict[str, Any], request_id: str) -> tuple[str, ...]:
    """The task id when this is an Agent step, plus the mailbox request id."""
    keys: list[str] = []
    body = message.get("body")
    if isinstance(body, dict) and body.get("task_id"):
        keys.append(str(body["task_id"]))
    if message.get("task_id"):
        keys.append(str(message["task_id"]))
    if request_id:
        keys.append(str(request_id))
    return tuple(dict.fromkeys(keys))


class StreamTail:
    """Follow one stream file until the caller says the step has finished."""

    def __init__(self, key: str, emit: Callable[[dict[str, Any]], None] | None = None) -> None:
        self.key = key
        self._emit = emit or emit_live
        self.offset = 0
        self.text = ""
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"linope-stream-{key[:8]}", daemon=True)

    def start(self) -> None:
        # The follower runs on another thread. Copy the caller's emitter now;
        # a context variable would not cross that thread boundary.
        if self._emit is emit_live:
            current = _emitter.get()
            if current is not None:
                self._emit = current
        path = stream_path(self.key)
        path.unlink(missing_ok=True)
        self._thread.start()

    def finish(self) -> str:
        self._stop.set()
        self._thread.join(timeout=1)
        self._drain()
        stream_path(self.key).unlink(missing_ok=True)
        return self.text

    def _run(self) -> None:
        while not self._stop.wait(0.05):
            self._drain()
        self._drain()

    def _drain(self) -> None:
        with self._lock:
            path = stream_path(self.key)
            try:
                data = path.read_text(encoding="utf-8")
            except OSError:
                return
            if not data.endswith("\n"):
                newline = data.rfind("\n")
                if newline < 0:
                    return
                data = data[: newline + 1]
            if len(data) < self.offset:
                self.offset = 0
            chunk = data[self.offset :]
            self.offset = len(data)
            events: list[dict[str, Any]] = []
            for line in chunk.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    events.append(event)
                    if event.get("type") == "text-delta":
                        self.text += str(event.get("text") or "")
        for event in events:
            self._emit(event)


def _append(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()
