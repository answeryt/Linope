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
    ) -> None:
        self.activation = activation
        self.status = ProcessStatus.CREATED
        self._book = book
        self._stopped = False
        self._child: subprocess.Popen[str] | None = None
        self._lines: queue.Queue[str] | None = None
        self._os_pid = 0
        self._secret_copy = ""
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
        if self._os_pid:
            return self._os_pid
        child = self._child
        if child is not None and child.pid:
            return int(child.pid)
        return 0

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
        """Start this capability in its own program and wait until it is ready."""
        if self._stopped or self._child is not None:
            return
        payload = self._child_payload()
        child = subprocess.Popen(
            [sys.executable, "-m", "kernel.process.process_runtime"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=_child_env(self._secret_names()),
            cwd=str(_repo_root()),
        )
        self._child = child
        assert child.stdin is not None
        child.stdin.write(json.dumps({"activation": payload}, ensure_ascii=False) + "\n")
        child.stdin.flush()
        ready = _read_line(child, timeout)
        if not ready:
            self._mark_dead()
            raise RuntimeError("这个能力的程序没有准备好")
        try:
            reply = json.loads(ready)
        except json.JSONDecodeError as exc:
            self._mark_dead()
            raise RuntimeError("这个能力的程序没有准备好") from exc
        if reply.get("event") != "ready":
            self._mark_dead()
            raise RuntimeError(str(reply.get("error") or "这个能力的程序没有准备好"))
        self._os_pid = int(child.pid or 0)
        self.status = ProcessStatus.RUNNING
        if self._book is not None:
            from kernel.process.process_manager.liveness import process_identity

            self._book.note_os(
                self.activation.process_id,
                self._os_pid,
                process_identity(self._os_pid) or "",
            )

    def ask(
        self,
        message: dict[str, Any],
        timeout: float | None = 10.0,
        on_notice: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any] | None:
        """Send one line and wait for its reply.

        ``timeout`` is how long a ping may stay quiet. ``None`` waits until the
        reply arrives or this process ends. A quiet wait does not close it.
        Text fragments are handed to ``on_notice`` and are not the reply.
        """
        if self._child is None:
            if message.get("operation") == "ping":
                return self.answer_ping(message, timeout=timeout if timeout is not None else 1.0)
            return _reply_for(message)
        if not self.is_alive:
            return None
        child = self._child
        if child.stdin is None:
            self._mark_dead()
            return None
        try:
            child.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
            child.stdin.flush()
        except OSError:
            self._mark_dead()
            return None
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            raw = self._take_line(remaining)
            if raw is None:
                return None
            if raw == "":
                self._mark_dead()
                return None
            if not raw.strip():
                continue
            try:
                reply = json.loads(raw)
            except json.JSONDecodeError:
                self._mark_dead()
                return None
            if not isinstance(reply, dict):
                self._mark_dead()
                return None
            chosen = _reply_line(message, reply, on_notice)
            if chosen is not None:
                return chosen

    def answer_ping(self, message: dict[str, Any], timeout: float = 1.0) -> dict[str, Any] | None:
        """Reply only when this process is the one being asked. Otherwise wait and stay quiet."""
        started = time.monotonic()
        target = str(message.get("process_id") or self.activation.process_id)
        asked = str(message.get("channel") or "")
        mine = self.channel_name()
        if (
            not self.is_alive
            or target != self.activation.process_id
            or (asked and mine and asked != mine)
        ):
            remaining = timeout - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)
            return None
        return {
            "event": "pong",
            "process_id": self.activation.process_id,
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
            process_id=self.activation.process_id,
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
        process_id = self.activation.process_id
        if self._book is not None:
            self._book.close(process_id)
        if self._pool is not None:
            self._pool.release(process_id)

    def revoke(self, handle: str) -> dict[str, object]:
        """Invalidate one handle through the resource pool."""
        if self._pool is None:
            raise RuntimeError("这个进程没有资源池")
        revocation = self._pool.revoke(handle)
        return {
            "handle": revocation.handle,
            "process_id": revocation.process_id,
            "resource_id": revocation.resource_id,
        }


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
        process_id = self.activation.process_id
        if self._book is not None:
            self._book.close(process_id)
        if self._pool is not None:
            self._pool.release(process_id)

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
            self.activation.process_id,
            activity,
            counterpart,
            way,
        )

    def _child_payload(self) -> dict[str, Any]:
        payload = self.activation.payload()
        environment = self.activation.environment
        names = self._secret_names()
        source = "" if environment is None else environment.env_file
        if not source or not names:
            shell = payload.get("environment")
            if isinstance(shell, dict):
                shell["inherit_parent_env"] = False
            return payload
        dest = _repo_root() / ".linope" / "secrets" / self.activation.process_id
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


def _reply_for(message: dict[str, Any]) -> dict[str, Any]:
    return {"event": "result", "operation": message.get("operation")}


def _reply_line(
    message: dict[str, Any],
    reply: dict[str, Any],
    on_notice: Callable[[dict[str, Any]], None] | None,
) -> dict[str, Any] | None:
    """A text fragment is shown and skipped. A late pong is not this load's reply."""
    if "event" not in reply and reply.get("type") in {"text", "text-delta"}:
        if on_notice is not None:
            on_notice(reply)
        return None
    event = reply.get("event")
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
    return env


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
