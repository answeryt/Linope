"""Move turns between the three lines and run the waits beside the model."""

from __future__ import annotations

import contextvars
import json
import shlex
import threading
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any

from kernel.scheduler.model_scheduler.book import Book
from kernel.scheduler.model_scheduler.cores import Cores, get_cores


@dataclass
class Turn:
    """One user sentence talking to one process."""

    key: str
    process: Any
    message: dict[str, Any]
    kind: str
    body: Any
    keep: bool
    line: str
    sender: Any | None = None
    phase: str = "listen"
    pending: str = ""
    marked: bool = False
    worker: threading.Thread | None = None
    task: Any = None
    core: int | None = None
    helpers: list[str] = field(default_factory=list)
    pending_signals: list[dict[str, str]] = field(default_factory=list)
    accepting_signal: bool = False


@dataclass
class Drive:
    """Step open turns for an explicit kernel runtime."""

    runtime: Any
    book: Book = field(default_factory=Book)
    cores: Cores = field(default_factory=get_cores)
    turns: dict[str, Turn] = field(default_factory=dict)
    mailbox: Queue[tuple[str, str, Any, str]] = field(default_factory=Queue)
    _seq: int = 0
    _announced: tuple[int, ...] = ()
    _parents: dict[str, str] = field(default_factory=dict)

    @property
    def model(self) -> Any:
        """Compatibility access to the first model core."""

        return self.cores.model

    def busy(self) -> bool:
        return bool(self.turns)

    def admit_load(
        self,
        process: Any,
        message: dict[str, Any],
        kind: str,
        body: Any,
        keep: bool,
        line: str,
    ) -> None:
        self._open(
            process,
            message,
            kind=kind,
            body=body,
            keep=keep,
            line=line,
            sender=None,
        )

    def admit_ask(self, sender: Any, receiver: Any, task: str, line: str) -> None:
        from kernel.command.process.listen import _maybe_relieve, _note, _pid_of, _remember

        _maybe_relieve(receiver)
        _remember(receiver, "user", task)
        sender_id = str(_pid_of(sender))
        receiver_id = str(_pid_of(receiver))
        _note(sender, "with", receiver_id, "task")
        _note(receiver, "with", sender_id, "task")
        self._open(
            receiver,
            {
                "operation": "load",
                "kind": "message",
                "body": task,
                "pid": _pid_of(receiver),
            },
            kind="message",
            body=task,
            keep=True,
            line=line,
            sender=sender,
        )

    def step(self) -> None:
        self._collect()
        self._poll()
        self._grant()
        self._sync_announce()

    def _open(
        self,
        process: Any,
        message: dict[str, Any],
        *,
        kind: str,
        body: Any,
        keep: bool,
        line: str,
        sender: Any | None,
    ) -> None:
        from kernel.thread.task import ensure_threads, note_arrival

        self._seq += 1
        task = note_arrival(process, body)
        if task.id in self.turns:
            task = ensure_threads(process).open()
        message = dict(message)
        message["turn_id"] = task.id
        turn = Turn(
            key=task.id,
            process=process,
            message=message,
            kind=kind,
            body=body,
            keep=keep,
            line=line,
            sender=sender,
            task=task,
        )
        self._emit("turn.started", {"kind": kind, "line": line}, turn=turn)
        self._mark(turn)
        self.turns[turn.key] = turn
        try:
            process.begin_exchange(message)
        except Exception as exc:
            self._finish(turn, error=str(exc) or type(exc).__name__)
            return
        turn.phase = "listen"

    def _mark(self, turn: Turn) -> None:
        others = [item for item in self.turns.values() if item is not turn]
        if not others:
            return
        turn.marked = True
        for item in others:
            item.marked = True

    def _collect(self) -> None:
        while True:
            try:
                key, kind, payload, error = self.mailbox.get_nowait()
            except Empty:
                return
            turn = self.turns.get(key)
            if turn is None:
                parent_key = self._parents.get(key)
                parent = None if parent_key is None else self.turns.get(parent_key)
                if parent is None:
                    continue
                self._land_helper(parent, key, "" if payload is None else str(payload), error)
                continue
            turn.worker = None
            if kind == "direct":
                self._finish_reply(turn, payload, error)
                continue
            self._say(turn, payload, error)
            if kind == "model":
                turn.phase = "after"
                continue
            if self.book.known(turn.key):
                self.book.finish_wait(turn.key)
            turn.core = None
            turn.phase = "listen"

    def _poll(self) -> None:
        for turn in list(self.turns.values()):
            if turn.phase not in {"listen", "after"}:
                continue
            if turn.worker is not None:
                continue
            try:
                reply = turn.process.next_line(0)
            except Exception as exc:
                self._finish(turn, error=str(exc) or type(exc).__name__)
                continue
            if reply is None:
                continue
            self._on_reply(turn, reply)

    def _on_reply(self, turn: Turn, reply: dict[str, Any]) -> None:
        event = reply.get("event")
        if event == "command":
            self._note_step(turn, reply)
            self._on_command(turn, str(reply.get("line") or ""))
            return
        if event == "fork":
            self._on_fork(turn, reply)
            return
        if event == "await":
            self._await_signal(turn)
            return
        self._finish_reply(turn, reply, "")

    def _note_step(self, turn: Turn, reply: dict[str, Any]) -> None:
        task = self._task_for(turn, str(reply.get("thread") or ""))
        program_counter = str(reply.get("pc") or "")
        registers = reply.get("registers") if isinstance(reply.get("registers"), dict) else None
        if program_counter:
            task.move(program_counter, registers)
            return
        if registers:
            task.registers.update(registers)

    def _task_for(self, turn: Turn, task_id: str) -> Any:
        from kernel.thread.task import ensure_threads

        if turn.task is not None and (not task_id or task_id == turn.task.id):
            return turn.task
        table = ensure_threads(turn.process)
        found = table.get(task_id) if task_id else None
        if found is None:
            found = turn.task if turn.task is not None else table.first
        turn.task = found
        return found

    def _on_fork(self, turn: Turn, reply: dict[str, Any]) -> None:
        from kernel.thread.task import ensure_threads

        self._note_step(turn, reply)
        task = turn.task
        if task is not None and not reply.get("pc"):
            task.move("wait_helpers")
        self.book.begin_wait(turn.key)
        turn.core = None
        turn.phase = "wait"
        turn.accepting_signal = True
        table = ensure_threads(turn.process)
        ready: list[tuple[str, str, str]] = []
        for item in reply.get("threads") or []:
            if not isinstance(item, dict):
                continue
            registers = dict(item.get("registers") or {})
            child = table.open(
                task_id=str(item.get("id") or ""),
                registers=registers,
                program_counter=str(item.get("pc") or "wait_tool"),
            )
            if child.program_counter != "wait_tool":
                child.move("wait_tool")
            line = str(item.get("line") or registers.get("command") or "")
            turn.helpers.append(child.id)
            self._parents[child.id] = turn.key
            if line:
                self._start_key(child.id, "io", line)
            else:
                ready.append((
                    child.id,
                    str(registers.get("result") or ""),
                    str(registers.get("error") or ""),
                ))
        for task_id, result, error in ready:
            self._land_helper(turn, task_id, result, error)
        if turn.accepting_signal and turn.pending_signals:
            self._deliver_signal(turn)
            return
        if turn.accepting_signal and not turn.helpers:
            self._close_signal(turn, "[]")

    def _land_helper(self, turn: Turn, task_id: str, result: str, error: str) -> None:
        from kernel.thread.task import ensure_threads

        task = ensure_threads(turn.process).get(task_id)
        if task is not None:
            task.registers["result"] = result
            task.registers["error"] = error
            task.move("done")
        self._parents.pop(task_id, None)
        turn.helpers = [item for item in turn.helpers if item != task_id]
        turn.pending_signals.append({"thread": task_id, "result": result, "error": error})
        self._deliver_signal(turn)

    def _await_signal(self, turn: Turn) -> None:
        """The loop is ready for the next completion. One signal, the earliest."""

        turn.accepting_signal = True
        turn.phase = "wait"
        self.book.begin_wait(turn.key)
        turn.core = None
        if turn.pending_signals:
            self._deliver_signal(turn)
            return
        if not turn.helpers:
            self._close_signal(turn, "[]")

    def _deliver_signal(self, turn: Turn) -> None:
        """Hand the loop the earliest finished helper, and leave the rest queued."""

        if not turn.accepting_signal or turn.phase != "wait" or not turn.pending_signals:
            return
        item = turn.pending_signals.pop(0)
        self._close_signal(turn, json.dumps([item], ensure_ascii=False))

    def _close_signal(self, turn: Turn, payload: str) -> None:
        turn.accepting_signal = False
        turn.phase = "listen"
        if self.book.known(turn.key):
            self.book.finish_wait(turn.key)
        turn.core = None
        self._say(turn, payload, "")

    def _on_command(self, turn: Turn, line: str) -> None:
        turn.accepting_signal = False
        if is_model_line(self.runtime, line):
            turn.pending = line
            if turn.task is not None:
                turn.task.move("ask_model", command=line)
            if turn.phase == "after":
                turn.phase = "using"
                if turn.task is not None:
                    turn.task.move("using_model", command=line)
                self._note_model(turn)
                self._start_model(turn)
                return
            if self.book.state(turn.key) != "ready":
                self.book.admit(turn.key)
            turn.phase = "want"
            self._grant()
            return
        self._begin_io(turn, line)

    def _begin_io(self, turn: Turn, line: str) -> None:
        from kernel.command.process.listen import _note

        self.book.begin_wait(turn.key)
        turn.core = None
        turn.phase = "wait"
        if turn.task is not None:
            turn.task.move("wait_tool", command=line)
        counterpart, way = _wait_target(line)
        _note(turn.process, "with", counterpart, way)
        self._start(turn, "io", line)

    def _grant(self) -> None:
        while True:
            free = self.cores.free_ids(self.book)
            if not free:
                return
            key = next(
                (
                    item
                    for item in self.book.ready_keys()
                    if (turn := self.turns.get(item)) is not None
                    and turn.phase == "want"
                ),
                None,
            )
            if key is None:
                return
            turn = self.turns[key]
            core = free[0]
            if self.book.grant(core, key) is None:
                return
            turn.core = core
            turn.phase = "using"
            if turn.task is not None:
                turn.task.move("using_model")
            self._note_model(turn)
            self._start_model(turn)

    def _note_model(self, turn: Turn) -> None:
        from kernel.command.process.listen import _note

        _note(turn.process, "self")
        self._emit("process.activity", {"activity": "working"}, turn=turn)

    def _start(self, turn: Turn, kind: str, line: str) -> None:
        self._start_key(turn.key, kind, line, owner=turn)

    def _start_model(self, turn: Turn) -> None:
        from kernel.command.process.listen import _notice_handler

        if turn.core is None:
            raise RuntimeError("model_core_not_assigned")
        model = self.cores.model_for(turn.core)
        context = contextvars.copy_context()

        def work() -> None:
            error = ""
            result: Any = None
            try:
                body = _model_body(turn.pending)
                result = model.run(
                    body,
                    on_notice=_notice_handler(self.runtime, turn.process),
                )
            except Exception as exc:
                error = str(exc) or type(exc).__name__
            self.mailbox.put((turn.key, "model", result, error))

        thread = threading.Thread(
            target=lambda: context.run(work),
            name=turn.key,
            daemon=True,
        )
        turn.worker = thread
        thread.start()

    def _start_key(self, key: str, kind: str, line: str, owner: Turn | None = None) -> None:
        context = contextvars.copy_context()

        def work() -> None:
            error = ""
            result = ""
            try:
                result = self.run_command(line)
            except Exception as exc:
                error = str(exc) or type(exc).__name__
            self.mailbox.put((key, kind, result, error))

        thread = threading.Thread(target=lambda: context.run(work), name=key, daemon=True)
        if owner is not None:
            owner.worker = thread
        thread.start()

    def run_command(self, line: str) -> Any:
        from kernel.command.process.clerk import execute_line

        return execute_line(line, self.runtime)

    def _say(self, turn: Turn, result: Any, error: str) -> None:
        reply = getattr(turn.process, "reply_command", None)
        if reply is None:
            return
        reply(result, error)

    def _finish_reply(self, turn: Turn, reply: Any, error: str) -> None:
        if error:
            self._finish(turn, error=error)
            return
        if not isinstance(reply, dict):
            self._finish(turn, error="This process is gone")
            return
        event = reply.get("event")
        if event in {"closed", "error"}:
            self._finish(turn, error=str(reply.get("error") or "This process is gone"))
            return
        self._finish(turn, result=reply.get("result"))

    def _finish(self, turn: Turn, result: Any = None, error: str = "") -> None:
        from kernel.command.process.listen import (
            _keep_output,
            _note,
            _output_text,
            _pid_of,
            _remember,
        )

        if turn.key not in self.turns:
            return
        if turn.task is not None:
            turn.task.move("done")
        end = getattr(turn.process, "end_exchange", None)
        if end is not None:
            try:
                end()
            except Exception:
                pass
        self.book.finish(turn.key)
        turn.core = None
        if getattr(turn.process, "is_alive", False):
            _note(turn.process, "sleeping")
            self._emit("process.activity", {"activity": "sleeping"}, turn=turn)
        if turn.sender is not None and getattr(turn.sender, "is_alive", False):
            _note(turn.sender, "sleeping")
        self.turns.pop(turn.key, None)
        if error:
            self._emit(
                "turn.completed",
                {"error": {"code": "turn_failed", "message": error}},
                turn=turn,
            )
        else:
            if turn.keep:
                _keep_output(turn.process, turn.kind, turn.body, result)
            if turn.sender is not None:
                _remember(turn.sender, "other", _output_text(result))
            self._emit("turn.completed", {"result": result}, turn=turn)
        closer = getattr(self.runtime, "close_once", None)
        if closer is not None and turn.line:
            closer(turn.line)

    def _sync_announce(self) -> None:
        busy_cores = tuple(sorted(self.book.using_cores()))
        if busy_cores == self._announced:
            return
        self._announced = busy_cores
        self._emit(
            "model.slot",
            {
                "busy": bool(busy_cores),
                "core": busy_cores[0] if len(busy_cores) == 1 else None,
                "busy_cores": list(busy_cores),
                "count": self.cores.count,
                "cores": self.cores.count,
            },
        )

    def _emit(self, kind: str, data: dict[str, Any], *, turn: Turn | None = None) -> None:
        from kernel.command.process.listen import _pid_of

        emitter = getattr(self.runtime, "emit", None)
        if not callable(emitter):
            return
        emitter(
            kind,
            data,
            turn_id="" if turn is None else turn.key,
            pid=None if turn is None else _pid_of(turn.process),
        )


def is_model_process(process: Any) -> bool:
    """Compatibility predicate; models are no longer capability processes."""

    del process
    return False


def is_model_line(runtime: Any, line: str) -> bool:
    del runtime
    head, separator, _body = str(line).partition(" -- ")
    if not separator:
        return False
    try:
        return shlex.split(head) == ["model", "run"]
    except ValueError:
        return False


def _model_body(line: str) -> Any:
    _head, separator, body = str(line).partition(" -- ")
    if not separator:
        raise ValueError("usage: model run -- <body>")
    raw = body.strip()
    if raw.startswith(("{", "[")):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return body
    return body


def _wait_target(line: str) -> tuple[str, str]:
    from kernel.command.convention import UsageError
    from kernel.command.process.listen import parse_line

    try:
        parsed = parse_line(line)
    except UsageError:
        return "", "io"
    if parsed[0] == "load" and parsed[1] == "tool":
        return str(parsed[3]), "tool"
    if parsed[0] == "load":
        return str(parsed[3]), "io"
    return "", "io"

