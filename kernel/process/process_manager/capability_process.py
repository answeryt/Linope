"""One capability process view."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kernel.environment.identity import copy_named_secrets, sensitive_name
from kernel.process.process_creat.activation import ProcessActivation
from kernel.process.process_manager.lifecycle import ProcessStatus
from kernel.process.resource_record import ProcessResourceBook
from kernel.resource.lease import ResourceLeaseManager
from kernel.resource.pool import ResourcePool

_READY_TIMEOUT = 5.0


class CapabilityProcess:
    """One peer process addressed by its activation."""

    def __init__(
        self,
        activation: ProcessActivation,
        *,
        resource_pool: ResourcePool | None = None,
        lease_manager: ResourceLeaseManager | None = None,
        book: ProcessResourceBook | None = None,
        child: subprocess.Popen[str] | None = None,
    ) -> None:
        self.activation = activation
        self.status = ProcessStatus.CREATED
        self._book = book
        self._stopped = False
        self._child = child
        self._lines: queue.Queue[str] | None = None
        self._os_pid = int(activation.pid)
        self._ready = False
        self._secret_copy = ""
        self._talk = threading.Lock()
        self._in_talk = False
        self._on_notice: Callable[[dict[str, Any]], None] | None = None
        self._exchange_message: dict[str, Any] = {}
        self._buffered: dict[str, Any] | None = None
        self.adapter: Any | None = None
        if resource_pool is not None:
            self._pool = resource_pool
        elif lease_manager is not None:
            self._pool = ResourcePool(lease_manager)
        else:
            self._pool = None

    @property
    def is_alive(self) -> bool:
        return not self._stopped

    @property
    def pid(self) -> int:
        return int(self.activation.pid)

    @property
    def handle(self):
        """Return the client-only view."""
        from kernel.process.process_manager.handle import ProcessHandle

        return ProcessHandle(self)

    def channel_name(self) -> str:
        """The network channel this process asked for. Empty when it has none."""
        for grant in self.activation.grants:
            kind = str(getattr(grant.kind, "value", grant.kind))
            if kind != "network":
                continue
            identity = dict((grant.metadata or {}).get("identity") or {})
            return str(identity.get("channel") or "")
        return ""

    def open_program(self, timeout: float = _READY_TIMEOUT) -> None:
        """Wait until a program that is already running is ready.

        The operating-system process is created before this account exists.
        Calling this again does not start a second program.
        """
        if self._stopped or self._ready:
            return
        child = self._child
        if child is None:
            return
        payload = self._child_payload()
        if child.stdin is None:
            self._abandon_child(child)
            raise RuntimeError("This capability's program is not ready")
        try:
            child.stdin.write(json.dumps({"activation": payload}, ensure_ascii=False) + "\n")
            child.stdin.flush()
        except OSError as exc:
            self._abandon_child(child)
            raise RuntimeError("This capability's program is not ready") from exc
        ready = _read_line(child, timeout)
        if not ready:
            self._abandon_child(child)
            raise RuntimeError("This capability's program is not ready")
        try:
            reply = json.loads(ready)
        except json.JSONDecodeError as exc:
            self._abandon_child(child)
            raise RuntimeError("This capability's program is not ready") from exc
        if reply.get("event") != "ready":
            self._abandon_child(child)
            raise RuntimeError(str(reply.get("error") or "This capability's program is not ready"))
        self._ready = True
        self._os_pid = int(self.activation.pid)
        self.status = ProcessStatus.RUNNING
        if self._book is not None:
            from kernel.process.process_manager.liveness import process_identity

            self._book.note_os(
                self.activation.pid,
                process_identity(self._os_pid) or "",
            )

    def ask(
        self,
        message: dict[str, Any],
        timeout: float | None = 10.0,
        on_notice: Callable[[dict[str, Any]], None] | None = None,
        on_command: Callable[[str], Any] | None = None,
    ) -> dict[str, Any] | None:
        """Send one line and wait for its reply.

        ``timeout`` is how long a ping may stay quiet. ``None`` waits until the
        reply arrives or this process ends. A quiet wait does not close it.
        Text fragments are handed to ``on_notice`` and are not the reply.
        A command from this process is run here before the wait continues.
        """
        if self._child is None:
            if message.get("operation") == "ping":
                return self.answer_ping(message, timeout=timeout if timeout is not None else 1.0)
            return _reply_for(message)
        if not self.begin_exchange(message, on_notice=on_notice, wait=timeout):
            return None
        try:
            deadline = None if timeout is None else time.monotonic() + float(timeout)
            while True:
                remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
                reply = self.next_line(remaining)
                if reply is None:
                    return None
                if reply.get("event") == "closed":
                    return None
                if reply.get("event") == "command":
                    _answer_command(self, reply, on_command)
                    continue
                return reply
        finally:
            self.end_exchange()

    def begin_exchange(
        self,
        message: dict[str, Any],
        on_notice: Callable[[dict[str, Any]], None] | None = None,
        *,
        wait: float | None = 0,
    ) -> bool:
        """Send one line and keep the conversation open until ``end_exchange``.

        ``wait`` is how long to stand in line for this process. ``0`` tries
        once and raises when somebody else is already talking. ``None`` waits
        until the line is free. A positive number waits at most that many
        seconds and returns False when the line stays busy.
        """

        if not self._acquire_talk(wait):
            return False
        self._in_talk = True
        self._on_notice = on_notice
        self._exchange_message = dict(message)
        self._buffered = None
        try:
            self._hand_off(message)
        except Exception:
            self.end_exchange()
            raise
        return True

    def _acquire_talk(self, wait: float | None) -> bool:
        """Take the one conversation this process can hold."""

        if wait == 0:
            if self._talk.acquire(blocking=False):
                return True
            raise RuntimeError("This process is already being asked")
        if wait is None:
            self._talk.acquire()
            return True
        if wait < 0:
            raise ValueError("wait must be >= 0")
        return bool(self._talk.acquire(timeout=float(wait)))

    def next_line(self, timeout: float | None) -> dict[str, Any] | None:
        """The next command or final reply. ``None`` means nothing arrived yet."""

        if self._buffered is not None:
            reply = self._buffered
            self._buffered = None
            return reply
        if not self._in_talk:
            return None
        deadline = None if timeout is None else time.monotonic() + float(timeout)
        while True:
            remaining: float | None
            if deadline is None:
                remaining = None
            else:
                remaining = max(0.0, deadline - time.monotonic())
            raw = self._take_line(0 if timeout == 0 else remaining)
            if raw is None:
                return None
            reply = self._read_reply(raw)
            if reply is None:
                continue
            return reply

    def reply_command(self, result: Any = None, error: str = "", thread: str = "") -> None:
        """Hand one command result back later. The conversation stays open."""

        child = self._child
        if child is None or child.stdin is None:
            return
        _write_command_result(child, result, error, thread)

    def end_exchange(self) -> None:
        """Let somebody else talk to this process."""

        if not self._in_talk:
            return
        self._in_talk = False
        self._on_notice = None
        self._exchange_message = {}
        self._buffered = None
        self._talk.release()

    def answer_ping(self, message: dict[str, Any], timeout: float = 1.0) -> dict[str, Any] | None:
        """Reply only when this process is the one being asked. Otherwise wait and stay quiet."""
        started = time.monotonic()
        target = int(message.get("pid") or self.activation.pid)
        asked = str(message.get("channel") or "")
        mine = self.channel_name()
        if (
            not self.is_alive
            or target != int(self.activation.pid)
            or (asked and mine and asked != mine)
        ):
            remaining = timeout - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)
            return None
        return {
            "event": "pong",
            "pid": self.activation.pid,
            "seq": message.get("seq"),
            "channel": mine,
        }

    def submit(self, message: dict[str, Any], timeout: float = 10.0) -> Any:
        """Accept one call. A one-shot call does not add a resource line."""
        from kernel.process.process_manager.client import Receipt

        request_id = str(message.get("request_id") or "local")
        if self._child is not None or message.get("operation") == "ping":
            self._reply = self.ask(message, timeout=timeout)
        else:
            self._reply = _reply_for(message)
        return Receipt(
            request_id=request_id,
            pid=self.activation.pid,
            _lookup=lambda _request_id: {"status": "done", "reply": self._reply},
            _wait=lambda _receipt, _timeout, caller_id=None: self._reply,
        )

    def wait(self, receipt: Any, timeout: float = 10.0) -> dict[str, Any]:
        del timeout
        return receipt.wait()

    def stop(self, timeout: float | None = None) -> None:
        """Close this process's resource account and return its leases."""
        if self._stopped:
            return
        self._note_activity("closed")
        self._stopped = True
        self.status = ProcessStatus.STOPPED
        child = self._child
        self._child = None
        if child is not None:
            if child.stdin is not None:
                try:
                    child.stdin.close()
                except OSError:
                    pass
            try:
                child.wait(timeout=timeout or 2)
            except subprocess.TimeoutExpired:
                child.kill()
        secret = self._secret_copy
        self._secret_copy = ""
        if secret:
            Path(secret).unlink(missing_ok=True)
        adapter = self.adapter
        self.adapter = None
        if adapter is not None:
            from kernel.process.process_runtime.runtime import close_adapter

            close_adapter(adapter)
        pid = self.activation.pid
        from kernel.thread.task import close_process_threads

        close_process_threads(pid)
        self.threads = None
        if self._book is not None:
            self._book.close(pid)
        if self._pool is not None:
            self._pool.release(pid)

    def revoke(self, handle: str) -> dict[str, object]:
        """Invalidate one handle through the resource pool."""
        if self._pool is None:
            raise RuntimeError("This process has no resource pool")
        revocation = self._pool.revoke(handle)
        if self._book is not None:
            self._book.drop_handle(int(revocation.pid), revocation.handle)
        return {
            "handle": revocation.handle,
            "pid": revocation.pid,
            "resource_id": revocation.resource_id,
        }

    def _abandon_child(self, child: subprocess.Popen[str]) -> None:
        self._child = None
        if child.poll() is None:
            child.kill()

    def _hand_off(self, message: dict[str, Any]) -> None:
        if self._child is None:
            self._buffered = _reply_for(message)
            return
        if not self.is_alive:
            self._buffered = {"event": "closed"}
            return
        child = self._child
        if child.stdin is None:
            self._mark_dead()
            self._buffered = {"event": "closed"}
            return
        try:
            child.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            child.stdin.flush()
        except OSError:
            self._mark_dead()
            self._buffered = {"event": "closed"}

    def _read_reply(self, raw: str) -> dict[str, Any] | None:
        """A command or a final reply. ``None`` is a fragment to skip."""

        if raw == "":
            self._mark_dead()
            return {"event": "closed"}
        if not raw.strip():
            return None
        try:
            reply = json.loads(raw)
        except json.JSONDecodeError:
            self._mark_dead()
            return {"event": "closed"}
        if not isinstance(reply, dict):
            self._mark_dead()
            return {"event": "closed"}
        if reply.get("event") == "command":
            return reply
        return _reply_line(self._exchange_message, reply, self._on_notice)

    def _take_line(self, timeout: float | None) -> str | None:
        """The next stdout line. ``None`` means the wait ended and the process is still up."""
        lines = self._ensure_reader()
        try:
            if timeout is None:
                return lines.get()
            return lines.get(timeout=timeout)
        except queue.Empty:
            return None

    def _ensure_reader(self) -> queue.Queue[str]:
        """One reader for this process. A timed-out wait must not start a second one."""
        if self._lines is not None:
            return self._lines
        child = self._child
        lines: queue.Queue[str] = queue.Queue()
        self._lines = lines

        def _pump() -> None:
            stdout = None if child is None else child.stdout
            try:
                while True:
                    raw = "" if stdout is None else stdout.readline()
                    lines.put(raw)
                    if not raw:
                        return
            except Exception:
                lines.put("")

        threading.Thread(target=_pump, daemon=True).start()
        return lines

    def _mark_dead(self) -> None:
        if self._stopped and self._child is None:
            return
        child = self._child
        self._child = None
        self._stopped = True
        self.status = ProcessStatus.STOPPED
        if child is not None and child.poll() is None:
            child.kill()
        self._note_activity("closed")
        secret = self._secret_copy
        self._secret_copy = ""
        if secret:
            Path(secret).unlink(missing_ok=True)
        pid = self.activation.pid
        if self._book is not None:
            self._book.close(pid)
        if self._pool is not None:
            self._pool.release(pid)

    def _secret_names(self) -> tuple[str, ...]:
        environment = self.activation.environment
        if environment is None:
            return ()
        return tuple(environment.env_file_keys)

    def _note_activity(self, activity: str, counterpart: str = "", way: str = "") -> None:
        book = self._book
        ledger = getattr(book, "_ledger", None) if book is not None else None
        if ledger is None:
            return
        from kernel.trace.activity import ActivityLog

        ActivityLog(Path(ledger.path).with_name("activity.jsonl")).append(
            self.activation.pid,
            activity,
            counterpart,
            way,
        )

    def _child_payload(self) -> dict[str, Any]:
        payload = self.activation.payload()
        ledger = None if self._book is None else getattr(self._book, "_ledger", None)
        if ledger is not None:
            payload["ledger_path"] = str(Path(ledger.path).resolve())
        environment = self.activation.environment
        names = self._secret_names()
        source = "" if environment is None else environment.env_file
        if not source or not names:
            shell = payload.get("environment")
            if isinstance(shell, dict):
                shell["inherit_parent_env"] = False
            return payload
        dest = _repo_root() / ".linope" / "secrets" / str(self.activation.pid)
        copy_named_secrets(source, names, dest)
        self._secret_copy = str(dest)
        shell = payload.get("environment")
        if isinstance(shell, dict):
            shell["env_file"] = str(dest)
            shell["inherit_parent_env"] = False
        room = payload.get("room")
        if isinstance(room, dict):
            identity = room.get("identity")
            if isinstance(identity, dict):
                identity["secret_file"] = str(dest)
                identity["secret_names"] = list(names)
        return payload


def _answer_command(
    process: CapabilityProcess,
    reply: dict[str, Any],
    on_command: Callable[[str], Any] | None,
) -> None:
    """Run one command line and hand its structured value back."""
    line = str(reply.get("line") or "")
    error = ""
    result: Any = None
    if on_command is None:
        error = "This process cannot run a command from here"
    else:
        try:
            result = on_command(line)
        except Exception as exc:
            error = str(exc) or type(exc).__name__
    process.reply_command(result, error)


def _write_command_result(
    child: subprocess.Popen[str],
    result: Any,
    error: str,
    thread: str = "",
) -> None:
    if child.stdin is None:
        return
    payload: dict[str, Any] = {"event": "command_result", "result": result, "error": error}
    if thread:
        payload["thread"] = thread
    child.stdin.write(
        json.dumps(payload, ensure_ascii=False)
        + "\n"
    )
    child.stdin.flush()


def _reply_for(message: dict[str, Any]) -> dict[str, Any]:
    return {"event": "result", "operation": message.get("operation")}


def _reply_line(
    message: dict[str, Any],
    reply: dict[str, Any],
    _on_notice: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any] | None:
    """A late pong is not this load's reply."""
    event = reply.get("event")
    if event == "notice":
        notice = reply.get("notice")
        if _on_notice is not None and isinstance(notice, dict):
            payload = dict(notice)
            if reply.get("turn_id"):
                payload.setdefault("turn_id", reply["turn_id"])
            if reply.get("pid"):
                payload.setdefault("pid", reply["pid"])
            _on_notice(payload)
        return None
    if message.get("operation") == "ping":
        if event == "pong" and reply.get("seq") == message.get("seq"):
            return reply
        if event == "pong":
            return None
        return reply
    if event == "pong":
        return None
    return reply


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _child_env(secret_names: tuple[str, ...]) -> dict[str, str]:
    hidden = set(secret_names)
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in hidden and not sensitive_name(key)
    }
    root = str(_repo_root())
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root if not current else root + os.pathsep + current
    env["PYTHONIOENCODING"] = "utf-8"
    env["LINOPE_COMMAND_DOOR"] = "1"
    return env


def spawn_runtime(
    secret_names: tuple[str, ...] = (),
    argv: tuple[str, ...] | list[str] | None = None,
    *,
    cwd: str | None = None,
    sandbox_policy: dict[str, Any] | None = None,
) -> subprocess.Popen[str]:
    """Start the command from the capability table."""
    if not argv:
        raise RuntimeError("This capability has no command")
    command = list(argv)
    program = Path(command[0]).name.lower()
    if program in {"python", "python.exe", "python3", "python3.exe"}:
        command[0] = sys.executable
    if command[0] == "node" and len(command) > 1:
        script = _repo_root() / command[1]
        if script.is_file():
            command[1] = str(script)
    working_directory = str(Path(cwd).expanduser().resolve()) if cwd else os.getcwd()
    if sandbox_policy:
        from kernel.environment.confine import host_isolator

        mode = str(sandbox_policy.get("mode") or "")
        if (
            mode != "danger-full-access"
            and str(sandbox_policy.get("scope") or "") != "host"
        ):
            wrapped = host_isolator(mode, sandbox_policy)(
                tuple(command),
                working_directory,
                str(sandbox_policy.get("cwd") or working_directory),
            )
            command = [str(item) for item in wrapped["argv"]]
    child = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
        text=True,
        encoding="utf-8",
        env=_child_env(secret_names),
        cwd=working_directory,
    )
    _drain_stderr(child)
    return child


def _drain_stderr(child: subprocess.Popen[str]) -> None:
    """Consume capability diagnostics without promoting them to UI output."""

    if child.stderr is None:
        return

    def drain() -> None:
        try:
            while child.stderr is not None and child.stderr.readline():
                pass
        except (OSError, ValueError):
            return

    threading.Thread(target=drain, name="linope-capability-stderr", daemon=True).start()


def _read_line(child: subprocess.Popen[str], timeout: float) -> str:
    if child.stdout is None:
        return ""
    found: dict[str, str] = {}

    def _read() -> None:
        found["line"] = child.stdout.readline() if child.stdout is not None else ""

    reader = threading.Thread(target=_read, daemon=True)
    reader.start()
    reader.join(timeout)
    if reader.is_alive():
        return ""
    return found.get("line", "")
