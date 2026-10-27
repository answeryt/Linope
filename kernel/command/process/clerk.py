"""One clerk for the whole window.

``process start`` opens a capability and returns the prompt. The capability
stays up. Later lines in this same clerk talk to it. The clerk closes every
capability only when the window leaves.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from kernel.command.convention import UsageError, guard
from kernel.command.process.listen import (
    PING_TIMEOUT,
    _open_programs,
    _startup_ping,
)
from kernel.command.process.start import _parse_start_options, launch_options
from kernel.command.window import bind_line, bind_window, reset_line, reset_window
from kernel.process.profile import ProfileUnavailable


class _Batch:
    def __init__(self, processes: tuple[Any, ...]) -> None:
        self._only = processes

    def processes(self) -> tuple[Any, ...]:
        return self._only


class Clerk:
    """The one place that starts capabilities and keeps their pipes."""

    def __init__(self) -> None:
        self._items: list[tuple[str, Any]] = []
        self._once: set[int] = set()
        self._env_file = ""
        self._book: Any = None
        self._pool: Any = None
        self._reconciler: Any = None
        self._closed = False

    def processes(self) -> tuple[Any, ...]:
        return tuple(process for _name, process in self._items)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for _name, process in self._items:
            try:
                process.stop()
            except Exception:
                pass

    def serve(self, lines: Any = None) -> int:
        """Read one command per line. ``exit`` or a closed pipe ends the clerk."""
        source = sys.stdin if lines is None else lines
        token = bind_window(self)
        try:
            for raw in source:
                if self._command(raw):
                    break
        except KeyboardInterrupt:
            pass
        finally:
            reset_window(token)
            self.close()
        return 0

    def _command(self, raw: str) -> bool:
        text = raw.strip()
        if not text:
            _done()
            return False
        _note_line(self, text)
        if text in {"exit", "quit"}:
            _done()
            return True
        try:
            argv = _split(text)
            if argv and argv[0] == "linope":
                argv = argv[1:]
                text = text.split(None, 1)[1].strip() if len(text.split(None, 1)) > 1 else ""
            from kernel.command.dispatch import main

            line = bind_line(text)
            try:
                main(argv)
            finally:
                reset_line(line)
        except (UsageError, ProfileUnavailable, ValueError, KeyError, RuntimeError, OSError) as exc:
            print(exc, file=sys.stderr)
        _done()
        return False

    def launch(self, argv: list[str]) -> tuple[Any, ...]:
        parsed = _parse_start_options(argv)
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
            thread_policy=options.thread_policy,
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
            print(
                f"pid={process.pid} capability={parsed[0]}",
                flush=True,
            )
        if parsed[2] and not _startup_ping(_Batch(tuple(batch)), PING_TIMEOUT):
            print("This process did not answer", file=sys.stderr)
            for process in batch:
                process.stop()
            return ()
        return tuple(batch)

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
        """Remember the env file later process starts in this window should use."""
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
    return Clerk().serve(lines)


@guard("usage: linope session")
def run(argv: list[str]) -> int:
    """Open the one window. ``linope terminal`` uses this same entry."""
    from kernel.command.window import current_window

    if current_window() is not None:
        print("Already in the terminal", flush=True)
        return 0
    if argv:
        raise UsageError("usage: linope session")
    return serve()


def _note_line(clerk: Clerk, text: str) -> None:
    """The line a person typed. It has no pid, so `log` without a pid is what shows it."""
    from kernel.trace.journal import Journal, journal_beside, journal_path

    book = clerk._book
    ledger = getattr(book, "_ledger", None) if book is not None else None
    path = journal_path() if ledger is None else journal_beside(ledger.path)
    Journal(path).append({"kind": "line", "text": text})


def _done() -> None:
    print(json.dumps({"type": "done"}, ensure_ascii=False), flush=True)


def _split(text: str) -> list[str]:
    import shlex

    return shlex.split(text, posix=True)
