"""Context, network, and communication numbers written when something happens."""

from __future__ import annotations

import json
from typing import Any

from kernel.resource.account.bind import current_store
from kernel.resource.account.embedded import Hold, holds
from kernel.resource.account.report import Line


def record_context(
    store: Any,
    process_id: str,
    *,
    occupied: int,
    ceiling: int | None,
    output_tokens: int,
) -> None:
    """Replace the window occupancy and add this call's output tokens."""
    current = _note(store, process_id, "context")
    fields = {
        "occupied": int(occupied),
        "output": int(current.get("output", 0)) + int(output_tokens),
    }
    if ceiling is not None:
        fields["ceiling"] = int(ceiling)
    elif "ceiling" in current:
        fields["ceiling"] = int(current["ceiling"])
    store.replace_note(process_id, "context", fields)


def record_network(
    store: Any,
    process_id: str,
    *,
    sent: int,
    received: int,
    requests: int = 1,
) -> None:
    """Add bytes and one request to the process that used the network."""
    store.add_note(
        process_id,
        "network",
        {
            "sent": int(sent),
            "received": int(received),
            "requests": int(requests),
        },
    )


def record_communication(store: Any, process_id: str, body: object) -> None:
    """Add the UTF-8 size of one sent body to that process."""
    if not process_id or not hasattr(store, "add_note"):
        return
    raw = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False, default=str)
    store.add_note(process_id, "communication", {"sent": len(raw.encode("utf-8"))})


def record_network_current(*, sent: int, received: int, requests: int = 1) -> None:
    """Charge the bound process, if this call is running inside one."""
    store = current_store()
    process_id = _current_process_id()
    if store is None or not process_id:
        return
    record_network(store, process_id, sent=sent, received=received, requests=requests)


def recorded_lines(store: Any, process_ids: tuple[str, ...] | None) -> tuple[Line, ...]:
    """Sum the notes for these processes. A missing note on a held lease is zero."""
    ids = _ids(store, process_ids)
    leased = holds(store, ids)
    lines: list[Line] = []
    for kind, builder in (
        ("context", _context_line),
        ("network", _network_line),
        ("communication", _communication_line),
    ):
        group = [
            line
            for process_id in ids
            if (line := builder(store, process_id, leased)) is not None
        ]
        merged = _merge(group)
        if merged is not None:
            lines.append(merged)
    return tuple(lines)


def _context_line(store: Any, process_id: str, leased: tuple[Hold, ...]) -> Line | None:
    del leased
    note = _note(store, process_id, "context")
    if not note:
        return None
    ceiling = note.get("ceiling")
    return Line(
        kind="context",
        used=int(note.get("occupied", 0)),
        ceiling=None if ceiling is None else int(ceiling),
        unit="tokens",
        detail=(("output", int(note.get("output", 0))),),
    )


def _network_line(store: Any, process_id: str, leased: tuple[Hold, ...]) -> Line | None:
    note = _note(store, process_id, "network")
    if not note and not _holds_kind(leased, process_id, "network"):
        return None
    sent = int(note.get("sent", 0))
    received = int(note.get("received", 0))
    requests = int(note.get("requests", 0))
    return Line(
        kind="network",
        used=sent + received,
        ceiling=None,
        unit="bytes",
        detail=(("sent", sent), ("received", received), ("requests", requests)),
    )


def _communication_line(
    store: Any,
    process_id: str,
    leased: tuple[Hold, ...],
) -> Line | None:
    note = _note(store, process_id, "communication")
    if not note and not _holds_kind(leased, process_id, "communication"):
        return None
    sent = int(note.get("sent", 0))
    return Line(
        kind="communication",
        used=sent,
        ceiling=None,
        unit="bytes",
        detail=(("sent", sent),),
    )


def _merge(group: list[Line]) -> Line | None:
    if not group:
        return None
    ceilings = [item.ceiling for item in group]
    ceiling = None if any(item is None for item in ceilings) else sum(
        int(item) for item in ceilings if item is not None
    )
    keys: list[str] = []
    for item in group:
        for name, _value in item.detail:
            if name not in keys:
                keys.append(name)
    return Line(
        kind=group[0].kind,
        used=sum(item.used for item in group),
        ceiling=ceiling,
        unit=group[0].unit,
        detail=tuple((key, sum(item.detail_of(key) for item in group)) for key in keys),
    )


def _ids(store: Any, process_ids: tuple[str, ...] | None) -> tuple[str, ...]:
    if process_ids is not None:
        return tuple(dict.fromkeys(process_ids))
    found: list[str] = []
    rows = getattr(getattr(store, "process", None), "rows", None)
    if callable(rows):
        found.extend(str(process_id) for process_id, _row in rows())
    found.extend(item.process_id for item in holds(store, None))
    noted = getattr(store, "noted_processes", None)
    if callable(noted):
        found.extend(str(process_id) for process_id in noted())
    return tuple(dict.fromkeys(process_id for process_id in found if process_id))


def _note(store: Any, process_id: str, kind: str) -> dict[str, int]:
    reader = getattr(store, "note", None)
    if not callable(reader):
        return {}
    raw = reader(process_id, kind)
    if not isinstance(raw, dict):
        return {}
    return {str(key): int(value) for key, value in raw.items()}


def _holds_kind(leased: tuple[Hold, ...], process_id: str, kind: str) -> bool:
    return any(item.process_id == process_id and item.kind == kind for item in leased)


def _current_process_id() -> str:
    try:
        from kernel.environment import current_room
    except Exception:
        return ""
    room = current_room()
    shell = getattr(room, "shell", None)
    return str(getattr(shell, "process_id", "") or "")
