"""Capability process loop."""

from __future__ import annotations

import sys
import threading
from contextvars import ContextVar
from collections.abc import Callable
from typing import Any

from kernel.environment import KernelEnvironment, bind_room
from kernel.environment.policy import HostExecutionPolicy
from kernel.environment.shell import ProcessEnvironment

_notice_writer: ContextVar[Callable[[dict[str, Any]], None] | None] = ContextVar(
    "linope_notice_writer",
    default=None,
)
_write_lock = threading.Lock()


def emit_notice(payload: dict[str, Any]) -> None:
    """Send one structured in-flight notice to the parent process."""

    writer = _notice_writer.get()
    if writer is not None:
        writer(dict(payload))


def _create_adapter(modules: list[Any]) -> Any | None:
    for module in modules:
        factory = getattr(module, "create_adapter", None)
        if factory is not None:
            return factory(modules)
    return None


def open_adapter(activation: dict[str, Any], modules: list[Any] | None = None) -> Any | None:
    """Bind the room and the modules the capability program already loaded."""
    from kernel.resource.handle_view import ResourceContext

    if not modules:
        raise RuntimeError("The capability program loads its own modules")
    room = _room_from_activation(activation)
    bind_room(room)
    adapter = None
    try:
        room.apply()
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


def serve_capability(
    activation: dict[str, Any],
    on_exit: Any | None = None,
    modules: list[Any] | None = None,
) -> None:
    """Close the resource account for modules the capability program already loaded."""
    adapter = None
    try:
        adapter = open_adapter(activation, modules)
    finally:
        close_adapter(adapter)
        if on_exit is not None:
            on_exit(int(activation["pid"]))


def serve_loaded(
    modules: list[Any],
    stdin: Any | None = None,
    stdout: Any | None = None,
) -> None:
    """Answer the kernel with modules the capability program already loaded."""
    serve_stdio(stdin, stdout, modules)


def serve_stdio(
    stdin: Any | None = None,
    stdout: Any | None = None,
    modules: list[Any] | None = None,
) -> None:
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
        _write_line(outgoing, {"event": "error", "error": "The startup message does not name this capability"})
        return
    adapter = None
    try:
        adapter = open_adapter(activation, modules)
    except Exception as exc:
        _write_line(outgoing, {"event": "error", "error": str(exc)})
        return
    pid = int(activation.get("pid") or 0)
    _write_line(outgoing, {"event": "ready", "pid": pid})
    try:
        _serve_steps(incoming, outgoing, adapter, activation, pid)
    finally:
        close_adapter(adapter)


def _serve_steps(
    incoming: Any,
    outgoing: Any,
    adapter: Any | None,
    activation: dict[str, Any],
    pid: int,
) -> None:
    """Each request is one step of this process's thread."""

    import json

    from kernel.thread.task import open_process_threads

    leader_id = str(activation.get("thread_id") or pid)
    table = open_process_threads(pid, first_id=leader_id)
    thread = table.first
    while True:
        raw = incoming.readline()
        if not raw:
            return
        if not str(raw).strip():
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            _write_line(outgoing, {"event": "error", "error": str(exc), "thread": thread.id})
            continue
        if not isinstance(message, dict):
            _write_line(outgoing, {"event": "error", "error": "The request must be one record", "thread": thread.id})
            continue
        thread.move("wait_tool", operation=str(message.get("operation") or ""))
        token = _notice_writer.set(
            lambda notice: _write_line(
                outgoing,
                {
                    "event": "notice",
                    "pid": pid,
                    "turn_id": str(message.get("turn_id") or ""),
                    "thread": thread.id,
                    "notice": notice,
                },
            )
        )
        try:
            reply = _dispatch(adapter, message, pid)
        finally:
            _notice_writer.reset(token)
        thread.move("done")
        reply["thread"] = thread.id
        _write_line(outgoing, reply)


def _dispatch(adapter: Any | None, message: dict[str, Any], pid: int) -> dict[str, Any]:
    import inspect

    operation = message.get("operation")
    if operation == "ping":
        if "pid" in message and int(message.get("pid") or 0) != pid:
            return {"event": "error", "error": "This is not this capability's pid"}
        return {
            "event": "pong",
            "pid": pid,
            "seq": message.get("seq"),
            "channel": str(message.get("channel") or ""),
        }
    if adapter is None or not (hasattr(adapter, "handle") or hasattr(adapter, "handle_async")):
        return {"event": "error", "error": "This process has no load"}
    payload = {key: value for key, value in message.items() if key != "request_id"}
    try:
        handler = getattr(adapter, "handle_async", None)
        if handler is None or not _adapter_is_async(adapter):
            handler = adapter.handle
        result = handler(payload)
        if inspect.isawaitable(result):
            import asyncio

            result = asyncio.run(result)
    except Exception as error:
        return {
            "event": "error",
            "error_type": type(error).__name__,
            "error": str(error),
        }
    return {"event": "result", "result": result}


def _adapter_is_async(adapter: Any) -> bool:
    import inspect

    explicit = getattr(adapter, "is_async", None)
    if explicit is not None:
        return bool(explicit)
    return inspect.iscoroutinefunction(getattr(adapter, "handle_async", None))


def _use_utf8(stream: Any) -> None:
    """The parent reads and writes this pipe as UTF-8."""
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    reconfigure(encoding="utf-8")


def _write_line(outgoing: Any, payload: dict[str, Any]) -> None:
    import json

    with _write_lock:
        outgoing.write(json.dumps(payload, ensure_ascii=False) + "\n")
        outgoing.flush()


def _room_from_activation(activation: dict[str, Any]) -> KernelEnvironment:
    raw = activation.get("room")
    if isinstance(raw, dict):
        return KernelEnvironment.from_payload(raw)
    shell = ProcessEnvironment.from_payload(activation["environment"])
    policy = HostExecutionPolicy.from_payload(activation.get("host_policy"))
    return KernelEnvironment.build(
        shell=shell,
        policy=policy,
        max_concurrent_tasks=1,
        max_sync_workers=1,
        module_paths=tuple(str(path) for path in activation.get("module_paths") or ()),
    )
