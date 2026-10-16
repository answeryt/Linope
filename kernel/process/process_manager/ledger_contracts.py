"""Protocols for process rows, sharing, layout, and the views composed from them."""

from __future__ import annotations

from typing import Any, Protocol

from kernel.communication.ledger_contracts import ChannelStore, RequestStore
from kernel.resource.store.contracts import LeaseStore, StoreIdentity


class ProcessStore(Protocol):
    def register_process(
        self,
        process_id: str,
        capability_id: str,
        pid: int | None,
        status: str,
    ) -> None:
        ...

    def update_process(
        self,
        process_id: str,
        *,
        pid: int | None = None,
        status: str,
        exit_code: int | None = None,
        identity: str | None = None,
    ) -> None:
        ...

    def get_process(self, process_id: str) -> dict[str, Any] | None:
        ...

    def set_activation(self, process_id: str, payload: dict[str, Any]) -> None:
        ...

    def activation_for(self, process_id: str) -> dict[str, Any]:
        ...

    def note_spawn_pid(self, process_id: str, pid: int) -> None:
        ...

    def set_desired(self, process_id: str, desired: str) -> None:
        ...

    def mark_running(
        self,
        process_id: str,
        pid: int,
        identity: str | None,
        ready: dict[str, Any],
    ) -> bool:
        ...

    def mark_failed(
        self,
        process_id: str,
        pid: int | None,
        identity: str | None,
        ready: dict[str, Any],
    ) -> None:
        ...

    def record_failure(self, process_id: str, message: str) -> None:
        ...


class ShareStore(Protocol):
    def shares_capability(self, capability_id: str) -> bool:
        ...

    def shared_capabilities(self) -> tuple[str, ...]:
        ...

    def share_capabilities(self, capability_ids: tuple[str, ...]) -> None:
        ...

    def clear_share(self) -> None:
        ...


class LayoutStore(Protocol):
    def selected_layout(self) -> tuple[str | None, dict[str, Any]]:
        ...

    def select_layout(
        self,
        name: str | None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        ...

    def set_replica_name(self, process_id: str, replica_name: str) -> None:
        ...

    def running_replicas(self, capability_id: str) -> tuple[dict[str, Any], ...]:
        ...


class ReapStore(Protocol):
    def reap_dead_processes(self) -> None:
        ...


class ReconcileStore(ProcessStore, ShareStore, LayoutStore, ChannelStore, Protocol):
    """The ledger view required to reconcile capability replicas."""


class ResourceRuntimeStore(
    LeaseStore,
    ProcessStore,
    RequestStore,
    ReapStore,
    StoreIdentity,
    Protocol,
):
    """The store view required by a running capability process."""
