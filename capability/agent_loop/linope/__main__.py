"""One capability process. A user message becomes kernel command lines.

The kernel starts this process, binds its resource record, and runs each
command the loop writes. This file keeps the stdin door open. A process can
hold several turns; each turn reads only the results marked with its thread.
"""

from __future__ import annotations

import json
import queue
import sys
import threading
import time
from typing import Any, Callable

from capability.agent_loop.linope.loop import CommandResult, Loop, adopt_remote_tools
from capability.tools.external_tools.mcp.mcp_tool_manager_plugin import discover_tools

_WRITE = threading.Lock()
_HUB_CAPABILITY = "tools.mcp_tool_manager"
Discover = Callable[[], list[dict[str, Any]]]


def main() -> None:
    """Answer ``load message`` until the pipe closes."""

    _use_utf8(sys.stdin)
    _use_utf8(sys.stdout)
    first = sys.stdin.readline()
    if not first:
        return
    try:
        startup = json.loads(first)
    except json.JSONDecodeError as exc:
        _write({"event": "error", "error": str(exc)})
        return
    activation = startup.get("activation")
    if not isinstance(activation, dict):
        _write({"event": "error", "error": "The startup message does not name this capability"})
        return
    pid = int(activation.get("pid") or 0)
    settings = _settings(activation)
    try:
        session = Loop(_without_hub(settings), _closed)
        session.bind(pid, str(activation.get("thread_id") or ""))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _write({"event": "error", "error": str(exc)})
        return
    _write({"event": "ready", "pid": pid, "threads": True})
    remote = _RemoteTools(_HUB_CAPABILITY) if _hub_enabled(settings) else None
    _Door(session, remote).serve()


class _RemoteTools:
    """One list from MCPHub. Turns wait, and the tools are installed once."""

    def __init__(self, capability: str, discover: Discover | None = None) -> None:
        self.capability = capability
        self._discover = discover or discover_tools
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._error: BaseException | None = None
        self._rows: list[dict[str, Any]] | None = None
        self._installed = False
        threading.Thread(target=self._fetch, name="linope-remote-tools", daemon=True).start()

    def _fetch(self) -> None:
        try:
            self._rows = self._discover()
        except Exception as exc:
            self._error = exc
        finally:
            self._ready.set()

    def install(self, session: Loop) -> None:
        """Block until the list is in, then add those tools to the shared table."""

        self._ready.wait()
        with self._lock:
            if self._installed:
                return
            if self._error is not None:
                raise self._error
            session.tools = adopt_remote_tools(session.tools, self.capability, self._rows or [])
            self._installed = True


class _Door:
    """Read stdin on one thread and give each turn the results marked with its thread."""

    def __init__(self, session: Loop, remote: _RemoteTools | None = None) -> None:
        self.session = session
        self.remote = remote
        self.inbox: queue.Queue[str | None] = queue.Queue()
        self.lock = threading.Lock()
        self.turns: dict[str, queue.Queue[CommandResult]] = {}

    def serve(self) -> None:
        threading.Thread(target=self._read, name="linope-agent-stdin", daemon=True).start()
        while True:
            raw = self.inbox.get()
            if raw is None:
                break
            try:
                self._dispatch(raw)
            except Exception as exc:
                _write({"event": "error", "error": str(exc)})
        self._join()

    def _read(self) -> None:
        while True:
            raw = sys.stdin.readline()
            if not raw:
                self.inbox.put(None)
                return
            self.inbox.put(raw)

    def _join(self) -> None:
        while True:
            with self.lock:
                if not self.turns:
                    return
            time.sleep(0.01)

    def _dispatch(self, raw: str) -> None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            _write({"event": "error", "error": str(exc)})
            return
        if not isinstance(message, dict):
            _write({"event": "error", "error": "The request must be one record"})
            return
        if message.get("event") == "command_result":
            self._deliver(message)
            return
        if message.get("operation") == "ping":
            _write({
                "event": "pong",
                "pid": self.session.pid,
                "seq": message.get("seq"),
                "channel": message.get("channel") or "",
            })
            return
        if message.get("operation") != "load" or message.get("kind") != "message":
            _write({"event": "error", "error": "This process only accepts load message"})
            return
        thread = str(message.get("thread") or "")
        if not thread:
            _write({"event": "error", "error": "This load has no thread"})
            return
        body = message.get("body")
        question = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
        turn = self._turn_for(thread)
        box = self._register(thread)
        turn.submit = _submit_for(box, thread)
        threading.Thread(
            target=self._run,
            args=(turn, question, thread),
            name=f"linope-turn-{thread}",
            daemon=True,
        ).start()

    def _turn_for(self, thread: str) -> Loop:
        """The kernel names the turn. The leader id keeps the first loop."""

        leader = self.session.thread_id or str(self.session.pid)
        if thread == leader:
            return self.session
        return self.session.open_turn(thread)

    def _register(self, thread: str) -> queue.Queue[CommandResult]:
        box: queue.Queue[CommandResult] = queue.Queue()
        with self.lock:
            self.turns[thread] = box
        return box

    def _deliver(self, message: dict[str, Any]) -> None:
        result = CommandResult(
            result=message.get("result"),
            error=str(message.get("error") or ""),
        )
        thread = str(message.get("thread") or "")
        with self.lock:
            box = self.turns.get(thread)
        if box is not None:
            box.put(result)

    def _run(self, turn: Loop, question: str, thread: str) -> None:
        try:
            if self.remote is not None:
                self.remote.install(self.session)
            _run_turn(turn, question, thread)
        except Exception as exc:
            _write({"event": "error", "thread": thread, "error": str(exc)})
        finally:
            with self.lock:
                self.turns.pop(thread, None)


def _run_turn(session: Loop, question: str, thread: str) -> None:
    session.prepare(question)
    while True:
        step = session.step()
        forks = step.get("forks")
        if forks:
            _write({
                "event": "fork",
                "thread": thread,
                "pc": step.get("pc") or "wait_helpers",
                "registers": step.get("registers") or {},
                "threads": [_public_fork(item) for item in forks],
            })
            _land_signal(session, _result_for(session))
            continue
        if step.get("await"):
            _write({
                "event": "await",
                "thread": thread,
                "pc": step.get("pc") or "wait_signal",
                "registers": step.get("registers") or {},
            })
            _land_signal(session, _result_for(session))
            continue
        _write({
            "event": "command",
            "thread": thread,
            "pc": step.get("pc") or "",
            "registers": step.get("registers") or {},
            "line": step.get("line") or "",
        })
        done = session.land(_result_for(session))
        if done is not None:
            _write({
                "event": "result",
                "thread": thread,
                "result": done,
                "rows": session.memory_rows(),
            })
            return


def _result_for(session: Loop) -> CommandResult:
    """The step line was written above. Side commands wait inside ``submit``."""

    reply = session.submit
    # The queue submit is installed on the turn. Reaching here means the door
    # already wrote the step line, so the next queued result belongs to it.
    box = _queue_of(reply)
    if box is None:
        raise RuntimeError("The kernel returned a broken command result")
    return box.get()


def _submit_for(box: queue.Queue[CommandResult], thread: str):
    def submit(line: str) -> CommandResult:
        _write({"event": "command", "thread": thread, "line": line})
        return box.get()

    submit.box = box
    return submit


def _queue_of(submit: Any) -> queue.Queue[CommandResult] | None:
    box = getattr(submit, "box", None)
    if isinstance(box, queue.Queue):
        return box
    return None


def _land_signal(session: Loop, reply: CommandResult) -> None:
    if reply.error:
        raise RuntimeError(reply.error)
    session.land_signal(reply.result)


def _public_fork(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id") or "",
        "pc": item.get("pc") or "wait_tool",
        "line": item.get("line") or "",
        "registers": item.get("registers") or {},
    }


def _closed(line: str) -> CommandResult:
    del line
    raise RuntimeError("This turn has no command door")


def _settings(activation: dict[str, Any]) -> dict[str, Any]:
    context = activation.get("resource_context")
    if not isinstance(context, dict):
        return {}
    settings = context.get("settings")
    return settings if isinstance(settings, dict) else {}


def _hub_enabled(settings: dict[str, Any]) -> bool:
    names = settings.get("tools") or []
    if not isinstance(names, list):
        return False
    return _HUB_CAPABILITY in [str(name) for name in names]


def _without_hub(settings: dict[str, Any]) -> dict[str, Any]:
    """The hub name enables MCPHub. It is not a tool the model can call."""

    names = settings.get("tools") or []
    if not isinstance(names, list):
        return settings
    kept = [name for name in names if str(name) != _HUB_CAPABILITY]
    if len(kept) == len(names):
        return settings
    return {**settings, "tools": kept}


def _write(payload: dict[str, Any]) -> None:
    with _WRITE:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def _use_utf8(stream: Any) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    reconfigure(encoding="utf-8")


if __name__ == "__main__":
    main()
