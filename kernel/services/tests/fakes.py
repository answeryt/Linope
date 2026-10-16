"""Stand-ins for the process layer, used by the services tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class Declaration:
    def __init__(self, capability: str) -> None:
        self.capability = capability


class Store:
    def __init__(self, shared: tuple[str, ...] = ()) -> None:
        self.shared = shared
        self.closed = False

    def shared_capabilities(self) -> tuple[str, ...]:
        return self.shared

    def share_capabilities(self, capability_ids: tuple[str, ...]) -> None:
        self.shared = tuple(capability_ids)

    def close(self) -> None:
        self.closed = True

    def selected_channel(self) -> tuple[None, dict]:
        return None, {}


class Process:
    def __init__(self, process_id: str, *, kind: str = "tool", identity: dict | None = None) -> None:
        grant = SimpleNamespace(
            kind=SimpleNamespace(value=kind),
            metadata={"identity": dict(identity or {"id": process_id})},
        )
        self.activation = SimpleNamespace(process_id=process_id, grants=(grant,))
        self.pid = 7
        self.is_alive = True
        self.stopped = False
        self.submitted: list[dict[str, Any]] = []

    def submit(self, message: dict[str, Any], timeout: float = 10.0, caller_id: str | None = None):
        del timeout, caller_id
        self.submitted.append(message)
        return SimpleNamespace(request_id=f"{self.activation.process_id}-{len(self.submitted)}")

    def wait(self, receipt, timeout: float = 10.0, caller_id: str | None = None) -> dict[str, Any]:
        del timeout, caller_id
        return {"event": "pong", "request_id": receipt.request_id}

    def stop(self) -> None:
        self.stopped = True
        self.is_alive = False


class Reconciler:
    """Launches one process per declaration, unless a capability is marked to fail."""

    def __init__(self, pool: Any) -> None:
        self.pool = pool
        self.launched: list[str] = []
        self.opened: list[Process] = []
        self.fail_on: set[str] = set()
        self.copies = 1

    def launch(self, declaration: Declaration, **kwargs: Any) -> tuple[Process, ...]:
        del kwargs
        name = declaration.capability
        self.launched.append(name)
        if name in self.fail_on:
            raise RuntimeError(f"起不来: {name}")
        processes = tuple(Process(f"{name}-{index}") for index in range(self.copies))
        self.opened.extend(processes)
        return processes


def load_declaration(capability: str, changes: tuple) -> tuple[Declaration, object]:
    del changes
    return Declaration(capability), object()
