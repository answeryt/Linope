"""Compatibility host for the kernel runtime.

``process start`` opens a capability and returns the prompt. The capability
stays up. Later lines in this same clerk talk to it. The clerk closes every
 capability only when the runtime closes.
"""

from __future__ import annotations

import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from kernel.command.convention import UsageError, guard
from kernel.command.events import (
    EventSink,
    KernelEvent,
    current_event_sink,
)
from kernel.command.process.listen import (
    PING_TIMEOUT,
    _open_programs,
    _startup_ping,
)
from kernel.command.process.start import _parse_start_options, launch_options
from kernel.process.profile import ProfileUnavailable


class _Batch:
    def __init__(self, processes: tuple[Any, ...]) -> None:
        self._only = processes

    def processes(self) -> tuple[Any, ...]:
        return self._only


class KernelRuntime:
    """Kernel-owned process, resource, and model runtime state."""

    def __init__(self, sink: EventSink | None = None) -> None:
        self._items: list[tuple[str, Any]] = []
        self._once: set[int] = set()
        self._env_file = ""
        self._book: Any = None
        self._pool: Any = None
        self._reconciler: Any = None
        self._closed = False
        self._tls = threading.local()
        self._drive: Any = None
        self.offers_turns = True
        self._sink = sink or current_event_sink()
        self._event_seq = 0
        self._request_seq = 0

    def emit(
        self,
        kind: str,
        data: dict[str, Any] | None = None,
        *,
        request_id: str = "",
        turn_id: str = "",
        pid: int | None = None,
    ) -> None:
        """Publish one host-neutral fact."""

        self._event_seq += 1
        self._sink.emit(
            KernelEvent(
                kind=kind,
                data=dict(data or {}),
                request_id=request_id,
                turn_id=turn_id,
                pid=pid,
                seq=self._event_seq,
            )
        )

    def processes(self) -> tuple[Any, ...]:
        return tuple(process for _name, process in self._items)

    @property
    def nested(self) -> bool:
        return bool(getattr(self._tls, "nested", False))

    @nested.setter
    def nested(self, value: bool) -> None:
        self._tls.nested = bool(value)

    @property
    def deferred(self) -> bool:
        return bool(getattr(self._tls, "deferred", False))

    @deferred.setter
    def deferred(self, value: bool) -> None:
        self._tls.deferred = bool(value)

    @property
    def drive(self) -> Any:
        if self._drive is None:
            from kernel.scheduler.model_scheduler.drive import Drive

            self._drive = Drive(self)
        return self._drive

    def admit_load(
        self,
        process: Any,
        message: dict[str, Any],
        kind: str,
        body: Any,
        keep: bool,
        line: str,
    ) -> None:
        """Keep this load on the model line instead of waiting here."""

        self.deferred = True
        self.drive.admit_load(process, message, kind, body, keep, line)

    def admit_ask(self, sender: Any, receiver: Any, task: str, line: str) -> None:
        """Keep this task on the model line instead of waiting here."""

        self.deferred = True
        self.drive.admit_ask(sender, receiver, task, line)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for _name, process in self._items:
            try:
                process.stop()
            except Exception:
                pass
            self.emit(
                "process.closed",
                {"capability": _name},
                pid=int(getattr(process, "pid", 0) or 0) or None,
            )

    def serve(self, lines: Any = None) -> int:
        """Read commands while a file read can lend the model to someone else."""

        source = sys.stdin if lines is None else lines
        self.emit("session.started", {"cwd": str(Path.cwd())})
        incoming: queue.Queue[Any] = queue.Queue()

        def pump() -> None:
            try:
                for raw in source:
                    incoming.put(raw)
            finally:
                incoming.put(_EOF)

        threading.Thread(target=pump, name="linope-runtime", daemon=True).start()
        leaving = False
        try:
            while True:
                self.drive.step()
                if leaving and not self.drive.busy():
                    break
                try:
                    raw = incoming.get(timeout=0.02)
                except queue.Empty:
                    continue
                if raw is _EOF:
                    leaving = True
                    continue
                if self._command(raw):
                    leaving = True
                self.drive.step()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                while self.drive.busy():
                    self.drive.step()
                    time.sleep(0.01)
            except KeyboardInterrupt:
                pass
            self.close()
            self.emit("session.closed", {})
        return 0

    def _command(self, raw: str) -> bool:
        text = raw.strip()
        if not text:
            return False
        self._request_seq += 1
        request_id = f"request-{self._request_seq}"
        _note_line(self, text)
        if text in {"exit", "quit"}:
            return not self.nested
        self.deferred = False
        try:
            result = self._execute_text(text, request_id=request_id)
        except (UsageError, ProfileUnavailable, ValueError, KeyError, RuntimeError, OSError) as exc:
            self.emit(
                "command.failed",
                {
                    "error": {
                        "code": type(exc).__name__,
                        "message": str(exc),
                    },
                    "command": text,
                },
                request_id=request_id,
            )
            result = None
        if self.nested:
            return False
        if self.deferred:
            self.emit(
                "command.accepted",
                {"command": text, "deferred": True},
                request_id=request_id,
            )
            self.deferred = False
            return False
        if result is not None:
            self.emit(
                "command.completed",
                {"command": text, "value": result},
                request_id=request_id,
            )
        return False

    def command(self, raw: str) -> bool:
        """Handle one explicit IPC command request."""

        return self._command(raw)

    def _execute_text(self, text: str, *, request_id: str = "") -> Any:
        """Run one command without selecting a presentation."""

        argv = _split(text)
        if argv and argv[0] == "linope":
            argv = argv[1:]
        from kernel.command.dispatch import main

        return main(
            argv,
            runtime=self,
            request={"request_id": request_id, "line": text},
        )

    def launch(self, argv: list[str]) -> dict[str, Any]:
        parsed = _parse_start_options(argv)
        if str(parsed[0]).startswith("model."):
            raise UsageError("Model capabilities use `model use`, not `process start`")
        if not parsed[4] and self._env_file:
            parsed = (*parsed[:4], self._env_file, *parsed[5:])
        options = launch_options(parsed)
        self._ensure(options.ledger_path)
        from kernel.process.profile import load_declaration

        declaration, definition = load_declaration(parsed[0], parsed[1])
        from kernel.process.declaration import append_chosen, stamp_memory_space

        declaration = stamp_memory_space(
            append_chosen(declaration, options.chosen),
            parsed[1],
        )
        started = self._reconciler.launch(
            declaration,
            definition=definition,
            shared=options.shared,
            replica_count=parsed[3],
            env_file=options.env_file,
            env_file_keys=options.env_file_keys,
            cwd=options.cwd,
            host_policy=options.host_policy,
        )
        batch = []
        for process in started:
            self._items.append((parsed[0], process))
            if options.once:
                self._once.add(int(process.pid))
            batch.append(process)
        try:
            _open_programs(_Batch(tuple(batch)))
        except Exception:
            for process in batch:
                process.stop()
            raise
        for process in batch:
            self.emit(
                "process.started",
                {"capability": parsed[0]},
                pid=int(process.pid),
            )
        if parsed[2] and not _startup_ping(_Batch(tuple(batch)), PING_TIMEOUT):
            for process in batch:
                process.stop()
            raise RuntimeError("process_not_responding")
        return {
            "processes": [
                {"pid": int(process.pid), "capability": parsed[0]}
                for process in batch
            ]
        }

    def _ensure(self, ledger_path: str | None) -> None:
        if self._reconciler is not None:
            return
        from kernel.process.ledger import ProcessLedger
        from kernel.process.reconcile import ProcessReconciler
        from kernel.process.resource_record import ProcessResourceBook
        from kernel.resource.lease import ResourceLeaseManager
        from kernel.resource.pool import ResourcePool
        from kernel.process.process_manager.liveness import reap_dead

        path = ledger_path or str(Path.cwd() / ".linope" / "processes.json")
        book = ProcessResourceBook(ProcessLedger(path))
        reap_dead(book)
        pool = ResourcePool(ResourceLeaseManager())
        self._book = book
        self._pool = pool
        self._reconciler = ProcessReconciler(pool, book)

    def note_env(self, path: str) -> None:
        """Remember the env file later process starts in this runtime should use."""
        self._env_file = path

    def close_once(self, text: str) -> None:
        for name, process in self._items:
            del name
            pid = int(process.pid)
            if pid in self._once and _line_names_pid(text, pid) and process.is_alive:
                process.stop()


def _line_names_pid(text: str, pid: int) -> bool:
    return re.search(rf"(?<!\d){int(pid)}(?!\d)", text) is not None


def serve(lines: Any = None) -> int:
    return KernelRuntime().serve(lines)


@guard("usage: linope session")
def run(argv: list[str]) -> int:
    """Launch the external session capability."""
    if argv:
        raise UsageError("usage: linope session")
    completed = subprocess.run(
        [sys.executable, "-m", "capability.session.terminal"],
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        check=False,
    )
    return int(completed.returncode)


def _note_line(runtime: KernelRuntime, text: str) -> None:
    """The line a person typed. It has no pid, so `log` without a pid is what shows it."""
    from kernel.trace.journal import Journal, journal_beside, journal_path

    book = runtime._book
    ledger = getattr(book, "_ledger", None) if book is not None else None
    path = journal_path() if ledger is None else journal_beside(ledger.path)
    Journal(path).append({"kind": "line", "text": text})


def execute_line(
    text: str,
    runtime: Any = None,
    *,
    service: Any = None,
    request_id: str = "",
) -> Any:
    """Run one command line against an explicit kernel runtime."""

    target = runtime if runtime is not None else service
    if target is not None and hasattr(target, "_execute_text"):
        previous = bool(getattr(target, "nested", False))
        target.nested = True
        try:
            return target._execute_text(text, request_id=request_id)
        finally:
            target.nested = previous
    raise RuntimeError("No kernel runtime is open")


_EOF = object()


def _split(text: str) -> list[str]:
    import shlex

    return shlex.split(text, posix=True)
