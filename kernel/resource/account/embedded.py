"""Bytes still embedded on memory, workspace, and tool leases.

A swapped page keeps its address and adds nothing. A page counts toward the
resource named by the link beside it, not toward an address that happens to
equal a resource id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel.resource.account.report import Line


PAGE_KINDS = ("memory", "workspace", "tool")


@dataclass(frozen=True)
class Hold:
    """One active lease the byte account can see."""

    resource_id: str
    kind: str
    process_id: str
    handle: str


def holds(store: Any, process_ids: tuple[str, ...] | None) -> tuple[Hold, ...]:
    """Active leases, optionally limited to these processes."""
    rows = getattr(store, "active_lease_rows", None)
    if not callable(rows):
        return ()
    wanted = None if process_ids is None else set(process_ids)
    found: list[Hold] = []
    for resource_id, entity, lease, handle in rows():
        process_id = str(getattr(lease, "process_id", "") or "")
        if wanted is not None and process_id not in wanted:
            continue
        found.append(
            Hold(
                resource_id=str(resource_id),
                kind=str(getattr(entity, "kind", "") or ""),
                process_id=process_id,
                handle=str(handle or ""),
            )
        )
    return tuple(found)


def linked_bytes(store: Any, resource_id: str) -> int:
    """Embedded bytes whose link names this resource. Swapped pages add nothing."""
    total = 0
    for page, link in _pages(store):
        if str(getattr(link, "resource_id", "") or "") != resource_id:
            continue
        if _embedded(page):
            total += int(page.size)
    return total


def byte_lines(store: Any, process_ids: tuple[str, ...] | None) -> tuple[Line, ...]:
    """One byte line for each page kind held in this scope."""
    chosen = holds(store, process_ids)
    lines: list[Line] = []
    for kind in PAGE_KINDS:
        kind_holds = tuple(item for item in chosen if item.kind == kind)
        if not kind_holds:
            continue
        lines.append(
            Line(
                kind=kind,
                used=_used(store, kind_holds),
                ceiling=_ceiling(store, kind_holds),
                unit="bytes",
            )
        )
    return tuple(lines)


def byte_ceiling(limits: dict[str, Any] | None) -> int | None:
    """The handle ceiling. Only ``bytes`` is a limit."""
    if not limits or "bytes" not in limits:
        return None
    return int(limits["bytes"])


def admits(used: int, incoming: int, ceiling: int | None) -> bool:
    """Whether another embedded body still fits. No ceiling always admits."""
    if ceiling is None:
        return True
    return used + incoming <= ceiling


def require_room(used: int, incoming: int, ceiling: int | None) -> None:
    """Refuse another embedded body when it does not fit under the ceiling."""
    if not admits(used, incoming, ceiling):
        raise PermissionError("用量到顶，不能再嵌进正文")


def _used(store: Any, kind_holds: tuple[Hold, ...]) -> int:
    handles = {item.handle for item in kind_holds if item.handle}
    resources = {item.resource_id for item in kind_holds}
    total = 0
    seen: set[str] = set()
    for page, link in _pages(store):
        address = str(getattr(page, "address", "") or "")
        if not address or address in seen or not _embedded(page):
            continue
        handle = str(getattr(link, "handle", "") or "")
        resource_id = str(getattr(link, "resource_id", "") or "")
        if (handle and handle in handles) or (not handle and resource_id in resources):
            seen.add(address)
            total += int(page.size)
    return total


def _ceiling(store: Any, kind_holds: tuple[Hold, ...]) -> int | None:
    values: list[int] = []
    for hold in kind_holds:
        limit = _grant_bytes(store, hold.process_id, hold.handle)
        if limit is None:
            return None
        values.append(limit)
    if not values:
        return None
    return sum(values)


def _grant_bytes(store: Any, process_id: str, handle: str) -> int | None:
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
        if not isinstance(grant, dict):
            continue
        if str(grant.get("handle") or "") != handle:
            continue
        return byte_ceiling(grant.get("limits") if isinstance(grant.get("limits"), dict) else None)
    return None


def _pages(store: Any) -> tuple[tuple[Any, Any], ...]:
    reader = getattr(store, "all_pages", None)
    if not callable(reader):
        return ()
    return tuple(reader())


def _embedded(page: Any) -> bool:
    embedded = getattr(page, "embedded", None)
    if callable(embedded):
        return bool(embedded())
    return True
