"""Talk to one capability process through the resource ledger."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, cast

from kernel.process.process_creat.activation import ProcessActivation
from kernel.process.process_creat.creator import ProcessCreator
from kernel.process.process_manager.delegation import delegating
from kernel.process.process_manager.client import Receipt
from kernel.process.process_manager.client import wait_first
from kernel.process.process_manager.reaper import ProcessReaper
from kernel.process.process_manager.lifecycle import ProcessStatus
from kernel.process.communication.channel import Channel
from kernel.process.communication.registry import open_channel
from kernel.process.process_manager.liveness import process_matches
from kernel.resource.pool import ResourcePool
from kernel.resource.lease import ResourceLeaseManager
from kernel.process.process_manager.ledger_contracts import ResourceRuntimeStore


class CapabilityProcess:
    """One peer process addressed by its ledger row.

    This compatibility facade is a client and lifecycle view, not a parent
    Agent.
    """

    def __init__(
        self,
        activation: ProcessActivation,
        *,
        resource_store: ResourceRuntimeStore | None = None,
        resource_pool: ResourcePool | None = None,
        lease_manager: ResourceLeaseManager | None = None,
        reap: Callable[[], None] | None = None,
    ) -> None:
        self.activation = activation
        self.status = ProcessStatus.CREATED
        if resource_pool is not None:
            self._pool = resource_pool
        elif lease_manager is not None:
            self._pool = ResourcePool(lease_manager)
        else:
            if resource_store is None:
                from kernel.process.ledger import open_store

                resource_store = open_store()
            self._pool = ResourcePool(resource_store)
        self._store = cast(ResourceRuntimeStore, self._pool.store)
        self._reap = reap or self._store.reap_dead_processes
        self._reaper = ProcessReaper(self._reap)
        self._channel: Channel | None = None
        self.ready_message: dict[str, Any] | None = None

    @property
    def pid(self) -> int | None:
        row = self._row()
        if row is None or row.get("pid") is None:
            return None
        return int(row["pid"])

    @property
    def handle(self):
        """Return the client-only view; lifecycle remains on this facade."""
        from kernel.process.process_manager.handle import ProcessHandle

        return ProcessHandle(self)

    @property
    def is_alive(self) -> bool:
        row = self._row()
        if row is None or row["status"] not in {"starting", "running"}:
            return False
        return process_matches(row.get("pid"), row.get("identity"))

    def start(self, timeout: float | None = None) -> dict[str, Any]:
        if self.status != ProcessStatus.CREATED:
            raise RuntimeError(f"Cannot start process in state {self.status}")
        store_locator = getattr(self._store, "locator", None)
        if not store_locator or str(store_locator).startswith("memory:"):
            raise RuntimeError("内存存储不能拉起独立进程，请使用文件或数据库存储")
        startup_timeout = (
            self.activation.host_policy.startup_timeout_seconds
            if timeout is None
            else timeout
        )
        process_id = self.activation.process_id
        self._store.set_activation(process_id, self.activation.payload())
        self.status = ProcessStatus.STARTING
        try:
            pid = ProcessCreator(str(store_locator)).spawn(process_id)
            self._store.note_spawn_pid(process_id, pid)
            deadline = time.monotonic() + startup_timeout
            while time.monotonic() < deadline:
                row = self._row()
                if row is None:
                    break
                if row["status"] == ProcessStatus.RUNNING.value and row.get("ready"):
                    self.status = ProcessStatus.RUNNING
                    ready = dict(row["ready"])
                    self.ready_message = ready
                    return ready
                if row["status"] == ProcessStatus.FAILED.value:
                    ready = row.get("ready") or {}
                    raise RuntimeError(ready.get("error", "Capability failed"))
                time.sleep(0.02)
            raise TimeoutError("Capability process did not become ready")
        except BaseException:
            self.status = ProcessStatus.FAILED
            try:
                self._store.set_desired(process_id, "stop")
            except Exception:
                pass
            self._pool.release(process_id)
            self._pool.notify(
                "process_exited",
                process_id=process_id,
                reason="failed",
            )
            try:
                self._store.update_process(
                    process_id,
                    status=ProcessStatus.FAILED.value,
                    exit_code=None,
                )
            except Exception:
                pass
            raise

    def submit(
        self,
        message: dict[str, Any],
        *,
        timeout: float = 10.0,
        caller_id: str | None = None,
    ) -> Receipt:
        """Write one business request and return a receipt. Do not wait here."""
        outgoing = self._resolve_receipts(dict(message), timeout, caller_id)
        self._authorize_use()
        row = self._row()
        if row is None or row["status"] != ProcessStatus.RUNNING.value:
            raise RuntimeError(f"Process is not running: {self.status}")
        request_id = self._open_channel().submit(
            self.activation.process_id,
            outgoing,
            sender_id=caller_id,
        )
        return Receipt(
            request_id=request_id,
            process_id=self.activation.process_id,
            _lookup=self._lookup_request,
            _wait=self.wait,
        )

    def wait(
        self,
        receipt: Receipt,
        timeout: float = 10.0,
        *,
        caller_id: str | None = None,
    ) -> dict[str, Any]:
        """Wait until this receipt has a reply, or raise on timeout."""
        if receipt.process_id != self.activation.process_id:
            return receipt._wait(receipt, timeout, caller_id=caller_id)
        with delegating(caller_id, self.activation.process_id):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                row = self._open_channel().lookup(receipt.request_id)
                if row is not None and row["status"] == "done":
                    result = row.get("reply")
                    if not isinstance(result, dict):
                        raise RuntimeError("Capability process closed before replying")
                    return result
                if not self.is_alive:
                    raise RuntimeError("Capability process closed before replying")
                time.sleep(0.02)
        raise TimeoutError(f"Capability process did not respond: {self.pid}")

    def send(self, message: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
        """Submit and wait. Stop is a desired state on the process row."""
        if message.get("operation") == "stop":
            self.stop(timeout)
            return {"event": "stopping", "pid": self.pid}
        return self.wait(self.submit(message, timeout=timeout), timeout)

    def stop(self, timeout: float | None = None) -> None:
        row = self._row()
        if row is None:
            self.status = ProcessStatus.STOPPED
            self._close_channel()
            return
        if row["status"] in {ProcessStatus.STOPPED.value, ProcessStatus.FAILED.value}:
            self.status = ProcessStatus(row["status"])
            self._close_channel()
            return
        shutdown_timeout = (
            self.activation.host_policy.graceful_shutdown_timeout_seconds
            if timeout is None
            else timeout
        )
        self.status = ProcessStatus.STOPPING
        self._store.set_desired(self.activation.process_id, "stop")
        deadline = time.monotonic() + shutdown_timeout
        while time.monotonic() < deadline:
            self._reap_if_dead()
            current = self._row()
            if current is None:
                break
            if current["status"] in {
                ProcessStatus.STOPPED.value,
                ProcessStatus.FAILED.value,
            }:
                self.status = (
                    ProcessStatus.STOPPED
                    if current["status"] == ProcessStatus.STOPPED.value
                    else ProcessStatus.FAILED
                )
                self._close_channel()
                return
            if not process_matches(current.get("pid"), current.get("identity")):
                self._reap()
                self.status = ProcessStatus.STOPPED
                self._close_channel()
                return
            time.sleep(0.02)
        raise TimeoutError(f"Capability process did not stop: {self.pid}")

    def revoke(self, handle: str) -> dict[str, Any]:
        """Invalidate one handle in the ledger. The process drops it on its next read."""
        revocation = self._pool.revoke(handle)
        return {
            "handle": revocation.handle,
            "process_id": revocation.process_id,
            "resource_id": revocation.resource_id,
        }

    def _open_channel(self) -> Channel:
        if self._channel is None:
            self._channel = open_channel(
                self._store,
                self.activation.payload().get("communication"),
            )
        return self._channel

    def _lookup_request(self, request_id: str) -> dict[str, Any] | None:
        return self._open_channel().lookup(request_id)

    def _close_channel(self) -> None:
        channel = self._channel
        self._channel = None
        if channel is None:
            return
        try:
            channel.close()
        except Exception:
            pass

    def _row(self) -> dict[str, Any] | None:
        return self._store.get_process(self.activation.process_id)

    def _reap_if_dead(self) -> None:
        self._reaper.reap_if_dead(self._row())

    def _resolve_receipts(
        self,
        value: Any,
        timeout: float,
        caller_id: str | None,
    ) -> Any:
        if isinstance(value, Receipt):
            return value.wait(timeout, caller_id=caller_id)
        if isinstance(value, dict):
            return {
                key: self._resolve_receipts(item, timeout, caller_id)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self._resolve_receipts(item, timeout, caller_id) for item in value
            ]
        if isinstance(value, tuple):
            return tuple(
                self._resolve_receipts(item, timeout, caller_id) for item in value
            )
        return value

    def _authorize_use(self) -> None:
        grants = getattr(self.activation, "resource_context", None)
        if grants is None:
            return
        for grant in grants.grants:
            self._pool.authorize(grant.handle)
