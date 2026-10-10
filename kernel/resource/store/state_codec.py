"""Encoding boundary for persisted resource-store state."""

from __future__ import annotations

from typing import Any, Protocol


class StateCodec(Protocol):
    def encode(self, store: Any) -> dict[str, Any]:
        ...

    def decode(self, store: Any, payload: dict[str, Any]) -> None:
        ...


class JsonStateCodec:
    """Use the domain store's stable JSON-compatible state representation."""

    def encode(self, store: Any) -> dict[str, Any]:
        return store.export_state()

    def decode(self, store: Any, payload: dict[str, Any]) -> None:
        store.import_state(payload)
