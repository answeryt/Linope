"""One admission pass over recorded requests.

The pass reads the service usage, process seats, and inflight notes that
already exist. It only changes a request between pending and reserved.
"""

from __future__ import annotations

import time
from typing import Any

from kernel.load_balancing.hints import Seat
from kernel.resource.account.view import service
from kernel.resource.memory.task_kind import TaskKind, task_kind_for

_LANE_RANK = {"interactive": 0, "next": 1, "timer": 2, "background": 3}


def cycle(store: Any, *, now: float | None = None) -> tuple[str, ...]:
    """Reserve the ready heads that fit this snapshot. Return their ids in order."""
    current = time.time() if now is None else float(now)
    rows = list(store.admission_rows())
    by_id = {str(row["request_id"]): row for row in rows}
    budget = _budget(store, _member_ids(store, rows))
    active = sum(1 for row in rows if row["status"] in {"reserved", "claimed"})
    served: set[str] = set()
    reserved: list[str] = []
    for request_id in _order(store, rows, by_id, current):
        row = by_id[request_id]
        service_key = str(row.get("service_key") or "")
        if service_key in served:
            continue
        members = _members(store, service_key)
        if _context_full(store, members, bool(row.get("followed"))):
            continue
        if not _members_have_room(store, members):
            continue
        if budget is not None and active >= budget:
            if not _preempt(store, rows, by_id, _rank(row.get("lane"))):
                continue
            active -= 1
            rows = list(store.admission_rows())
            by_id = {str(item["request_id"]): item for item in rows}
        if not store.reserve_request(request_id):
            continue
        reserved.append(request_id)
        served.add(service_key)
        active += 1
        row["status"] = "reserved"
    return tuple(reserved)


def _order(
    store: Any,
    rows: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    now: float,
) -> tuple[str, ...]:
    ready: list[tuple[int, int, int, str]] = []
    for row in rows:
        if row["status"] != "pending" or not row.get("scheduled"):
            continue
        decision = _readiness(store, row, by_id, now)
        if decision == "close":
            store.close_request(str(row["request_id"]))
            continue
        if decision != "ready":
            continue
        members = _members(store, str(row.get("service_key") or ""))
        ready.append(
            (
                _rank(row.get("lane")),
                _usage(store, members),
                _number(row["request_id"]),
                str(row["request_id"]),
            )
        )
    ready.sort()
    return tuple(item[-1] for item in ready)


def _readiness(
    store: Any,
    row: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    now: float,
) -> str:
    lane = str(row.get("lane") or "next")
    start_by = row.get("start_by")
    if lane == "timer":
        if start_by is None or now < float(start_by):
            return "wait"
    if lane == "interactive" and start_by is not None and now > float(start_by):
        return "close"
    depends_on = row.get("depends_on")
    if depends_on:
        parent = by_id.get(str(depends_on))
        if parent is None:
            parent = store.lookup_request(str(depends_on))
        if parent is None or parent.get("status") != "done":
            return "wait"
    return "ready"


def _preempt(
    store: Any,
    rows: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    incoming_rank: int,
) -> bool:
    victims = [
        row
        for row in rows
        if row["status"] == "reserved" and _rank(row.get("lane")) > incoming_rank
    ]
    if not victims:
        return False
    victims.sort(
        key=lambda row: (
            -_usage(store, _members(store, str(row.get("service_key") or ""))),
            -_number(row["request_id"]),
        )
    )
    victim_id = str(victims[0]["request_id"])
    if not store.requeue_request(victim_id):
        return False
    if victim_id in by_id:
        by_id[victim_id]["status"] = "pending"
    return True


def _budget(store: Any, process_ids: set[str]) -> int | None:
    noted: list[int] = []
    ceilings: list[int] = []
    for process_id in process_ids:
        if hasattr(store, "note"):
            note = store.note(process_id, "inflight") or {}
            if isinstance(note, dict) and "current" in note:
                noted.append(int(note["current"]))
        getter = getattr(store, "get_process", None)
        row = getter(process_id) if callable(getter) else None
        if isinstance(row, dict) and row.get("inflight_ceiling") is not None:
            ceilings.append(int(row["inflight_ceiling"]))
    if noted:
        return sum(noted)
    if ceilings:
        return sum(ceilings)
    return None


def _context_full(store: Any, members: tuple[str, ...], followed: bool) -> bool:
    if task_kind_for(followed=followed) is not TaskKind.OCCUPY or not members:
        return False
    try:
        report = service(store, members)
    except Exception:
        return False
    line = report.line("context")
    return line is not None and line.ceiling is not None and line.used >= line.ceiling


def _members_have_room(store: Any, members: tuple[str, ...]) -> bool:
    if not members or not hasattr(store, "capability_seats"):
        return True
    found = False
    for process_id in members:
        getter = getattr(store, "get_process", None)
        row = getter(process_id) if callable(getter) else None
        if not isinstance(row, dict):
            continue
        capability = str(row.get("capability_id") or "")
        if not capability:
            continue
        try:
            raw = store.capability_seats(capability)
        except Exception:
            return True
        for item in raw:
            if str(item.get("process_id")) != process_id:
                continue
            found = True
            try:
                seat = Seat(**item)
            except TypeError:
                return True
            if seat.has_room:
                return True
    return not found


def _usage(store: Any, members: tuple[str, ...]) -> int:
    if not members:
        return 0
    try:
        report = service(store, members)
    except Exception:
        return 0
    return sum(line.used for line in report.lines)


def _member_ids(store: Any, rows: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        found.update(_members(store, str(row.get("service_key") or "")))
    return found


def _members(store: Any, service_key: str) -> tuple[str, ...]:
    """Process ids for a service name, or the recorded process ids themselves."""
    lookup = getattr(store, "service_member_ids", None)
    if callable(lookup):
        found = lookup(service_key)
        if found is not None:
            return tuple(found)
    return tuple(part for part in service_key.split(",") if part)


def _rank(lane: Any) -> int:
    return _LANE_RANK.get(str(lane or "next"), 1)


def _number(request_id: Any) -> int:
    try:
        return int(request_id)
    except (TypeError, ValueError):
        return 0
