"""The ledger the running capability process should charge."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any


_store: ContextVar[Any] = ContextVar("linope_account_store", default=None)


def bind_store(store: Any) -> Token[Any]:
    """Remember the ledger for later charges inside this process."""
    return _store.set(store)


def reset_store(token: Token[Any]) -> None:
    """Drop the ledger remembered by :func:`bind_store`."""
    _store.reset(token)


def current_store() -> Any | None:
    """The ledger bound for this process, or none outside a capability process."""
    return _store.get()
