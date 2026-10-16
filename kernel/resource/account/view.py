"""Reports for the whole machine, one service, and one process."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from kernel.resource.account.embedded import byte_ceiling, byte_lines, holds
from kernel.resource.account.recorded import recorded_lines
from kernel.resource.account.report import Line, Report
from kernel.resource.workspace.mount.view import inside


_ORDER = ("memory", "workspace", "tool", "context", "network", "communication")


def process(store: Any, process_id: str) -> Report:
    """Resources held or charged by this one process."""
    return _report(store, "process", (process_id,))


def service(store: Any, process_ids: Sequence[str]) -> Report:
    """Sum of the named member processes. Each embedded page is counted once."""
    return _report(store, "service", tuple(process_ids))


def total(store: Any) -> Report:
    """Every process on the ledger."""
    return _report(store, "total", None)


def workspace_room(store: Any, address: str) -> tuple[int, int | None, int]:
    """Used bytes, byte ceiling, and the size already counted for this address.

    The lease is the workspace whose project root contains ``address``.
    No such lease means there is no ceiling. ``counted`` is subtracted by
    the caller when the same embedded page is being replaced.
    """
    resolved = _resolved(address)
    chosen: tuple[str, str, str] | None = None
    for hold in holds(store, None):
        if hold.kind != "workspace" or not hold.handle:
            continue
        root = _root(store, hold.resource_id)
        if not root or not inside(root, resolved):
            continue
        if chosen is None or len(root) > len(chosen[0]):
            chosen = (root, hold.handle, hold.process_id)
    if chosen is None:
        return 0, None, 0
    _root_path, handle, process_id = chosen
    ceiling = _handle_ceiling(store, process_id, handle)
    used = 0
    counted = 0
    reader = getattr(store, "pages_for_handle", None)
    pairs = tuple(reader(handle)) if callable(reader) else ()
    for page, _link in pairs:
        embedded = getattr(page, "embedded", None)
        if not callable(embedded) or not embedded():
            continue
        size = int(getattr(page, "size", 0) or 0)
        used += size
        if _resolved(str(getattr(page, "address", ""))) == resolved:
            counted = size
    return used, ceiling, counted


def _report(
    store: Any,
    scope: str,
    process_ids: tuple[str, ...] | None,
) -> Report:
    by_kind: dict[str, Line] = {}
    for line in byte_lines(store, process_ids):
        by_kind[line.kind] = line
    for line in recorded_lines(store, process_ids):
        by_kind[line.kind] = line
    lines = tuple(by_kind[kind] for kind in _ORDER if kind in by_kind)
    return Report(scope=scope, lines=lines)


def _root(store: Any, resource_id: str) -> str:
    entity = store.entity(resource_id) if callable(getattr(store, "entity", None)) else None
    identity = getattr(entity, "identity", None) or {}
    if not isinstance(identity, dict):
        return ""
    return str(identity.get("root") or "")


def _handle_ceiling(store: Any, process_id: str, handle: str) -> int | None:
    getter = getattr(store, "get_process", None)
    process = getter(process_id) if callable(getter) else None
    if not isinstance(process, dict):
        return None
    activation = process.get("activation") or {}
    if not isinstance(activation, dict):
        return None
    context = activation.get("resource_context") or {}
    if not isinstance(context, dict):
        return None
    for grant in context.get("grants") or ():
        if isinstance(grant, dict) and str(grant.get("handle") or "") == handle:
            raw = grant.get("limits")
            return byte_ceiling(raw if isinstance(raw, dict) else None)
    return None


def _resolved(address: str) -> Path:
    candidate = Path(address)
    try:
        return candidate.expanduser().resolve()
    except OSError:
        return candidate.expanduser()


__all__ = [
    "process",
    "service",
    "total",
    "workspace_room",
]
