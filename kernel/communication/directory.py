"""Channel choice and listen addresses stored through the resource ledger."""

from __future__ import annotations

from pathlib import Path

from kernel.communication.ledger_contracts import ChannelStore


StoreReference = ChannelStore | str | Path


def selected_channel(store: StoreReference) -> tuple[str | None, dict[str, object]]:
    """Return the saved channel name and settings. Empty means the ledger default."""
    opened, owned = _open(store)
    try:
        return opened.selected_channel()
    finally:
        if owned:
            opened.close()


def select_channel(
    store: StoreReference,
    name: str | None,
    settings: dict[str, object] | None = None,
) -> None:
    """Remember one channel, or clear it when name is empty or off."""
    opened, owned = _open(store)
    try:
        opened.select_channel(name, settings)
    finally:
        if owned:
            opened.close()


def publish_endpoint(
    store: StoreReference,
    process_id: str,
    method: str,
    endpoint: str,
) -> None:
    """Record where one peer is listening. The business body stays off this table."""
    opened, owned = _open(store)
    try:
        opened.publish_endpoint(process_id, method, endpoint)
    finally:
        if owned:
            opened.close()


def endpoint_for(store: StoreReference, process_id: str) -> str | None:
    """Return the listen address published for this process, if it has one."""
    opened, owned = _open(store)
    try:
        return opened.endpoint_for(process_id)
    finally:
        if owned:
            opened.close()


def _open(store: StoreReference) -> tuple[ChannelStore, bool]:
    if not isinstance(store, (str, Path)):
        return store, False
    from kernel.process.ledger import open_store

    return open_store(store), True
