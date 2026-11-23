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
from typing import Any

from capability.agent_loop.linope.loop import CommandResult, Loop

_WRITE = threading.Lock()


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
    try:
        session = Loop(_settings(activation), _closed)
        session.bind(pid, str(activation.get("thread_id") or ""))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _write({"event": "error", "error": str(exc)})
        return
    _write({"event": "ready", "pid": pid, "threads": True})
    _Door(session).serve()


class _Door:
    """Read stdin on one thread and give each turn its own results."""

    def __init__(self, session: Loop) -> None:
        self.session = session
        self.inbox: queue.Queue[str | None] = queue.Queue()
        self.lock = threading.Lock()
        self.turns: dict[str, queue.Queue[CommandResult]] = {}
        self.pending: dict[str, list[CommandResult]] = {}
        self.running: set[str] = set()

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
                if not self.running:
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
        body = message.get("body")
        question = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
        thread = str(message.get("thread") or self.session.pid)
        turn = self._turn_for(thread)
        box = self._register(thread)
        turn.submit = _submit_for(box, thread)
        with self.lock:
            self.running.add(thread)
        threading.Thread(
            target=self._run,
            args=(turn, question, thread),
            name=f"linope-turn-{thread}",
            daemon=True,
        ).start()

    def _turn_for(self, thread: str) -> Loop:
        leader = self.session.thread_id or str(self.session.pid)
        with self.lock:
            busy = leader in self.running or str(self.session.pid) in self.running
        if thread in {leader, str(self.session.pid)} and not busy:
            return self.session
        return self.session.open_turn(thread)

    def _register(self, thread: str) -> queue.Queue[CommandResult]:
        box: queue.Queue[CommandResult] = queue.Queue()
        with self.lock:
            early = list(self.pending.pop(thread, []))
            if not self.turns:
                early.extend(self.pending.pop("", []))
            for item in early:
                box.put(item)
            self.turns[thread] = box
        return box

    def _deliver(self, message: dict[str, Any]) -> None:
        result = CommandResult(
            result=message.get("result"),
            error=str(message.get("error") or ""),
        )
        thread = str(message.get("thread") or "")
        with self.lock:
            if thread and thread in self.turns:
                self.turns[thread].put(result)
                return
            if not thread and len(self.turns) == 1:
                next(iter(self.turns.values())).put(result)
                return
            self.pending.setdefault(thread, []).append(result)

    def _run(self, turn: Loop, question: str, thread: str) -> None:
        try:
            _run_turn(turn, question, thread)
        except Exception as exc:
            _write({"event": "error", "thread": thread, "error": str(exc)})
        finally:
            with self.lock:
                self.running.discard(thread)
                self.turns.pop(thread, None)


def _run_turn(session: Loop, question: str, thread: str) -> None:
    session.prepare(question)
    while True:
        step = session.step()
        forks = step.get("forks")
        if forks:
            session.note_issued(item.get("id") for item in forks)
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
            _write({"event": "result", "thread": thread, "result": done})
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
