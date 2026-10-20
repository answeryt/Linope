"""Capability process loop."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from kernel.environment import KernelEnvironment, bind_room
from kernel.environment.policy import HostExecutionPolicy
from kernel.environment.shell import ProcessEnvironment
from kernel.thread.contracts import ThreadPolicy


def _load_modules(module_paths: tuple[str, ...], process_id: str = "") -> list[Any]:
    loaded = []
    for index, raw_path in enumerate(module_paths):
        path = Path(raw_path)
        name = f"capability_runtime_{process_id}_{index}_{path.stem}"
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
            str(activation.get("process_id") or ""),
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
            on_exit(str(activation["process_id"]))


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
    _write_line(
        outgoing,
        {"event": "ready", "process_id": str(activation.get("process_id") or "")},
    )
    try:
        for raw in incoming:
            if not raw.strip():
                continue
            try:
                message = json.loads(raw)
            except json.JSONDecodeError as exc:
                _write_line(outgoing, {"event": "error", "error": str(exc)})
                continue
            if not isinstance(message, dict):
                _write_line(outgoing, {"event": "error", "error": "请求必须是一条记录"})
                continue
            _write_line(outgoing, _answer(adapter, activation, message))
    finally:
        close_adapter(adapter)


def _answer(adapter: Any | None, activation: dict[str, Any], message: dict[str, Any]) -> dict[str, Any]:
    process_id = str(activation.get("process_id") or "")
    if str(message.get("process_id") or "") != process_id:
        return {"event": "error", "error": "这不是这个能力的进程号"}
    if message.get("operation") == "ping":
        return {
            "event": "pong",
            "process_id": process_id,
            "seq": message.get("seq"),
            "channel": str(message.get("channel") or ""),
        }
    if adapter is None:
        return {"event": "error", "error": "这个进程没有 load"}
    import asyncio

    try:
        result = asyncio.run(adapter.handle_async(message))
    except Exception as exc:
        return {"event": "error", "error": str(exc)}
    return {"event": "result", "result": result}


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
