"""Capability process loop. Looking at the ledger does not write it back."""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import time
from pathlib import Path
from typing import Any

from kernel.environment import KernelEnvironment, bind_room
from kernel.environment.policy import HostExecutionPolicy
from kernel.environment.shell import ProcessEnvironment
from kernel.process.process_manager.ledger_contracts import ResourceRuntimeStore
from kernel.thread.contracts import ThreadPolicy
from kernel.thread.inbox import ChannelInbox
from kernel.thread.runtime import ThreadRuntime, _adapter_is_async


def _load_modules(module_paths: tuple[str, ...]) -> list[Any]:
    loaded = []
    for index, raw_path in enumerate(module_paths):
        path = Path(raw_path)
        name = f"capability_runtime_{index}_{path.stem}"
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
            return factory()
    return None


def _shutdown(
    adapter: Any,
    store: ResourceRuntimeStore,
    process_id: str,
    *,
    failed: bool,
) -> None:
    if adapter is not None:
        adapter.shutdown()
    from kernel.resource.pool import ResourcePool

    ResourcePool(store).release(process_id)
    store.update_process(
        process_id,
        status="failed" if failed else "stopped",
        exit_code=1 if failed else 0,
    )


def _handle(message: dict[str, Any], adapter: Any) -> dict[str, Any]:
    operation = message.get("operation")
    if operation == "ping":
        return {"event": "pong", "pid": os.getpid()}
    if adapter is not None and hasattr(adapter, "handle"):
        payload = {
            key: value for key, value in message.items() if key != "request_id"
        }
        try:
            result = adapter.handle(payload)
        except Exception as error:
            return {
                "event": "error",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        return {"event": "result", "result": result}
    return {
        "event": "error",
        "error": f"No adapter is registered for {operation!r}",
    }


def serve_capability(
    store: ResourceRuntimeStore,
    activation: dict[str, Any],
) -> None:
    """Load one capability and serve ledger requests until asked to stop."""
    from kernel.process.process_manager.liveness import process_identity
    from kernel.resource.handle_view import ResourceContext

    from kernel.resource.account.bind import bind_store, reset_store

    process_id = str(activation["process_id"])
    identity = process_identity(os.getpid())
    adapter = None
    account_store = None
    store.update_process(
        process_id,
        pid=os.getpid(),
        status="starting",
        identity=identity,
    )
    try:
        account_store = bind_store(store)
        row = store.get_process(process_id)
        if row is not None and (
            row.get("desired") == "stop" or row.get("status") == "failed"
        ):
            _shutdown(adapter, store, process_id, failed=row.get("status") == "failed")
            return
        room = _room_from_activation(activation)
        bind_room(room)
        room.apply()
        environment = room.shell
        modules = _load_modules(tuple(activation["module_paths"]))
        resource_context = activation["resource_context"]
        adapter = _create_adapter(modules)
        if adapter is not None:
            adapter.initialize(ResourceContext.from_payload(resource_context), room)
        row = store.get_process(process_id)
        if row is not None and (
            row.get("desired") == "stop" or row.get("status") == "failed"
        ):
            _shutdown(adapter, store, process_id, failed=True)
            return
        from kernel.communication.registry import open_channel

        channel = open_channel(store, activation.get("communication"))
        try:
            channel.bind(process_id)
            started = store.mark_running(
                process_id,
                os.getpid(),
                identity,
                {
                    "event": "ready",
                    "pid": os.getpid(),
                    "process_id": process_id,
                    "capability_id": activation["instance_id"],
                    "resource_context": resource_context,
                    "cwd": environment.cwd,
                    "environment_keys": sorted(environment.env),
                    "env_file": environment.env_file,
                    "env_file_keys": list(environment.env_file_keys),
                    "sync_thread_safe": bool(
                        getattr(adapter, "sync_thread_safe", False)
                    ),
                    "is_async": _adapter_is_async(adapter),
                },
            )
            # #region agent log

            # #endregion
            if started is False:
                _shutdown(adapter, store, process_id, failed=False)
                return
            policy = ThreadPolicy.from_payload(activation.get("thread_policy"))
            inbox = ChannelInbox(channel)
            started_at = time.monotonic()

            async def should_stop() -> bool:
                if room.lifecycle.deadline_reached(started_at):
                    await asyncio.to_thread(
                        room.lifecycle.ask_stop,
                        store,
                        process_id,
                        started_at,
                    )
                    return True
                row = await asyncio.to_thread(_look_process, store, process_id)
                return (
                    row is None
                    or row.get("desired") == "stop"
                    or row.get("status") == "failed"
                )

            def staff_ceiling() -> int | None:
                row = _look_process(store, process_id)
                if row is None or row.get("worker_ceiling") is None:
                    return None
                return int(row["worker_ceiling"])

            def inflight_ceiling() -> int | None:
                row = _look_process(store, process_id)
                if row is None or row.get("inflight_ceiling") is None:
                    return None
                return int(row["inflight_ceiling"])

            def on_sample(elapsed: float, allowance: int | None) -> None:
                if not hasattr(store, "replace_note"):
                    return
                store.replace_note(
                    process_id,
                    "rtt",
                    {"ms": max(0, int(elapsed * 1000))},
                )
                if allowance is not None:
                    store.replace_note(
                        process_id,
                        "inflight",
                        {"current": int(allowance)},
                    )

            # #endregion
            asyncio.run(
                ThreadRuntime(policy).run(
                    process_id=process_id,
                    inbox=inbox,
                    adapter=adapter,
                    should_stop=should_stop,
                    staff_ceiling=staff_ceiling,
                    inflight_ceiling=inflight_ceiling,
                    on_sample=on_sample,
                )
            )
            row = _look_process(store, process_id)
            _shutdown(
                adapter,
                store,
                process_id,
                failed=bool(row and row.get("status") == "failed"),
            )
        finally:
            try:
                channel.close()
            except Exception:
                pass
    except BaseException as error:
        try:
            store.mark_failed(
                process_id,
                os.getpid(),
                identity,
                {
                    "event": "failed",
                    "pid": os.getpid(),
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )
        except Exception:
            pass
        try:
            from kernel.resource.pool import ResourcePool

            ResourcePool(store).release(process_id)
        except Exception:
            pass
        raise
    finally:
        if account_store is not None:
            reset_store(account_store)
        bind_room(None)


def _look_process(store: ResourceRuntimeStore, process_id: str) -> dict[str, Any] | None:
    """Ask whether to stop without rewriting the ledger."""
    peek = getattr(store, "peek_process", None)
    if callable(peek):
        return peek(process_id)
    return store.get_process(process_id)


def _room_from_activation(activation: dict[str, Any]) -> KernelEnvironment:
    raw = activation.get("room")
    if isinstance(raw, dict):
        return KernelEnvironment.from_payload(raw)
    shell = ProcessEnvironment.from_payload(activation["environment"])
    policy = HostExecutionPolicy.from_payload(activation.get("host_policy"))
    thread_policy = ThreadPolicy.from_payload(activation.get("thread_policy"))
    communication = activation.get("communication") or {}
    return KernelEnvironment.build(
        shell=shell,
        policy=policy,
        max_concurrent_tasks=thread_policy.max_concurrent_tasks,
        max_sync_workers=thread_policy.max_sync_workers,
        channel_name=str(communication.get("name") or "ledger"),
        channel_settings=dict(communication.get("settings") or {}),
        module_paths=tuple(str(path) for path in activation.get("module_paths") or ()),
    )
