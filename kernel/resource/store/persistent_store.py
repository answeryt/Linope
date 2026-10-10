"""Composition support for stores backed by an in-memory domain ledger."""

from __future__ import annotations

import functools
from typing import Any

from kernel.resource.store.state_codec import JsonStateCodec, StateCodec


class StateBackedStore:
    """Delegate domain operations while owning their persistence boundary.

    Domain behavior lives in ``_memory``.  Concrete adapters implement
    ``_run_operation`` to add a file lock or a database transaction.
    """

    def __init__(self, memory: Any, *, codec: StateCodec | None = None) -> None:
        self._memory = memory
        self._codec = codec or JsonStateCodec()

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        delegate = object.__getattribute__(self, "_memory")
        attr = getattr(delegate, name)
        if callable(attr):
            return functools.partial(
                object.__getattribute__(self, "_run_operation"),
                name,
            )
        return attr

    def export_state(self) -> dict[str, Any]:
        return self._codec.encode(self._memory)

    def import_state(self, payload: dict[str, Any]) -> None:
        self._codec.decode(self._memory, payload)

    def _delegate(self, name: str, *args: Any, **kwargs: Any) -> Any:
        return getattr(self._memory, name)(*args, **kwargs)

    def _run_operation(self, name: str, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError
