"""Capability process loop."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from kernel.environment import KernelEnvironment, bind_room
from kernel.environment.policy import HostExecutionPolicy
from kernel.environment.shell import ProcessEnvironment
from kernel.thread.contracts import ClaimedRequest, ThreadPolicy


def _load_modules(module_paths: tuple[str, ...], pid: int = 0) -> list[Any]:
    loaded = []
    for index, raw_path in enumerate(module_paths):
        path = Path(raw_path)
        name = f"capability_runtime_{pid}_{index}_{path.stem}"
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(name, None)
            raise
        loaded.append(module)
    return loaded


def _create_adapter(modules: list[Any]) -> Any | None:
    for module in modules:
        factory = getattr(module, "create_adapter", None)
        if factory is not None:
            return factory(modules)
    return None


def open_adapter(activation: dict[str, Any]) -> Any | None:
    """Load the capability and leave its adapter up until the process closes."""
    from kernel.resource.handle_view import ResourceContext

    room = _room_from_activation(activation)
    bind_room(room)
    adapter = None
    try:
        room.apply()
        modules = _load_modules(
            tuple(activation["module_paths"]),
            int(activation.get("pid") or 0),
        )
        adapter = _create_adapter(modules)
        if adapter is not None:
            adapter.initialize(
                ResourceContext.from_payload(activation["resource_context"]),
                room,
            )
        return adapter
    except Exception:
        close_adapter(adapter)
        raise


def close_adapter(adapter: Any | None) -> None:
    """Shut the adapter down. Closing twice is safe."""
    if adapter is None:
        return
    shutdown = getattr(adapter, "shutdown", None)
    if shutdown is not None:
        shutdown()
    bind_room(None)


def serve_capability(activation: dict[str, Any], on_exit: Any | None = None) -> None:
    """Load one capability from its activation, then close its resource account."""
    adapter = None
    try:
        adapter = open_adapter(activation)
    finally:
        close_adapter(adapter)
        if on_exit is not None:
            on_exit(int(activation["pid"]))


def serve_stdio(stdin: Any | None = None, stdout: Any | None = None) -> None:
    """Wait for one startup line, then answer each later line until the pipe closes.

    This program does not decide whether the caller stops after one job.
    """
    import json

    incoming = sys.stdin if stdin is None else stdin
    outgoing = sys.stdout if stdout is None else stdout
    _use_utf8(incoming)
    _use_utf8(outgoing)
    first = incoming.readline()
    if not first:
        return
    try:
        startup = json.loads(first)
    except json.JSONDecodeError as exc:
        _write_line(outgoing, {"event": "error", "error": str(exc)})
        return
    activation = startup.get("activation")
    if not isinstance(activation, dict):
        _write_line(outgoing, {"event": "error", "error": "启动信息里没有这个能力"})
        return
    adapter = None
    try:
        adapter = open_adapter(activation)
    except Exception as exc:
        _write_line(outgoing, {"event": "error", "error": str(exc)})
        return
    import asyncio
    import threading

    from kernel.thread.runtime import ThreadRuntime

    pid = int(activation.get("pid") or 0)
    write_lock = threading.Lock()

    def write(payload: dict[str, Any]) -> None:
        with write_lock:
            _write_line(outgoing, payload)

    write({"event": "ready", "pid": pid})
    inbox = _LineInbox(incoming, write, pid)
    policy = ThreadPolicy.from_payload(activation.get("thread_policy"))
    try:
        asyncio.run(
            ThreadRuntime(policy).run(
                process_id=str(pid),
                inbox=inbox,
                adapter=adapter,
                should_stop=inbox.closed,
                ceilings=_ledger_ceilings(activation, policy),
            )
        )
    finally:
        close_adapter(adapter)


class _LineInbox:
    """One stdin line is one claim. Replies go back out as lines."""

    def __init__(self, incoming: Any, write: Any, pid: int) -> None:
        self._incoming = incoming
        self._write = write
        self._pid = pid
        self.eof = False

    def claim(
        self,
        process_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> ClaimedRequest | None:
        del process_id, worker_id, lease_seconds
        import json
        import uuid

        while not self.eof:
            raw = self._incoming.readline()
            if not raw:
                self.eof = True
                return None
            if not str(raw).strip():
                continue
            try:
                message = json.loads(raw)
            except json.JSONDecodeError as exc:
                self._write({"event": "error", "error": str(exc)})
                continue
            if not isinstance(message, dict):
                self._write({"event": "error", "error": "请求必须是一条记录"})
                continue
            request_id = str(message.get("request_id") or uuid.uuid4().hex)
            return ClaimedRequest(
                request_id=request_id,
                process_id=str(self._pid),
                body=message,
            )
        return None

    def complete(
        self,
        request_id: str,
        reply: dict[str, Any],
        claim_token: str | None = None,
    ) -> None:
        del request_id, claim_token
        self._write(reply)

    def lookup(self, request_id: str) -> dict[str, Any] | None:
        del request_id
        return None

    def closed(self) -> bool:
        return self.eof


def ceilings_from_ledger(
    path: str,
    pid: int,
    fallback: tuple[int, int],
) -> tuple[int, int]:
    """Read this process's worker and inflight ceilings from its ledger row."""
    import json

    from kernel.process.ledger import ProcessLedger

    try:
        records = ProcessLedger(path).read()
    except (OSError, ValueError, json.JSONDecodeError):
        return fallback
    for record in records:
        if int(record.get("pid") or 0) != int(pid):
            continue
        room = record.get("room") if isinstance(record.get("room"), dict) else {}
        worker = room.get("worker_ceiling", fallback[0])
        inflight = room.get("inflight_ceiling", fallback[1])
        try:
            return int(worker), int(inflight)
        except (TypeError, ValueError):
            return fallback
    return fallback


def _ledger_ceilings(activation: dict[str, Any], policy: ThreadPolicy) -> Any:
    path = activation.get("ledger_path")
    if not path:
        return None
    pid = int(activation.get("pid") or 0)
    fallback = (policy.max_sync_workers, policy.max_concurrent_tasks)

    def read() -> tuple[int, int]:
        return ceilings_from_ledger(str(path), pid, fallback)

    return read


def _use_utf8(stream: Any) -> None:
    """The parent reads and writes this pipe as UTF-8."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    reconfigure(encoding="utf-8")


def _write_line(outgoing: Any, payload: dict[str, Any]) -> None:
    import json

    outgoing.write(json.dumps(payload, ensure_ascii=False) + "\n")
    outgoing.flush()


def _room_from_activation(activation: dict[str, Any]) -> KernelEnvironment:
    raw = activation.get("room")
    if isinstance(raw, dict):
        return KernelEnvironment.from_payload(raw)
    shell = ProcessEnvironment.from_payload(activation["environment"])
    policy = HostExecutionPolicy.from_payload(activation.get("host_policy"))
    thread_policy = ThreadPolicy.from_payload(activation.get("thread_policy"))
    return KernelEnvironment.build(
        shell=shell,
        policy=policy,
        max_concurrent_tasks=thread_policy.max_concurrent_tasks,
        max_sync_workers=thread_policy.max_sync_workers,
        module_paths=tuple(str(path) for path in activation.get("module_paths") or ()),
    )
