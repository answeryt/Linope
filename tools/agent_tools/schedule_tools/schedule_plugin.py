# -*- coding: utf-8 -*-
"""Session-local reminders: after_seconds, absolute at, or bounded every_seconds."""

from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional


PLUGIN_NAME = "schedule"
PLUGIN_VERSION = "1.0"

MIN_EVERY_SECONDS = 300

_SCHEDULES: dict[str, list[dict[str, Any]]] = {}
_LOCK = threading.Lock()


CREATE_SCHEMA: dict[str, Any] = {
    "name": "schedule_create",
    "description": (
        "Create one reminder in the current session. Supply a non-empty prompt "
        "and exactly one selector: a positive safe-integer after_seconds delay, "
        "at as a strict offset date-time or local date/time object, or "
        "safe-integer every_seconds of at least 300. Delivery is session-local."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Reminder content to present when the target becomes due.",
            },
            "after_seconds": {
                "type": "number",
                "description": "Positive safe-integer delay in seconds.",
            },
            "every_seconds": {
                "type": "number",
                "description": "Fixed-rate safe-integer interval in seconds, at least 300.",
            },
            "at": {
                "description": (
                    "Absolute target as strict offset RFC 3339 or local date/time "
                    "with an explicit IANA zone."
                ),
            },
        },
        "required": ["prompt"],
    },
}

DELETE_SCHEMA: dict[str, Any] = {
    "name": "schedule_delete",
    "description": (
        "Delete one active reminder in the current session by the exact id "
        "returned by schedule_create or schedule_list. Unknown or already-finished "
        "ids return deleted false."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Exact session-local schedule id."},
        },
        "required": ["id"],
    },
}

LIST_SCHEMA: dict[str, Any] = {
    "name": "schedule_list",
    "description": (
        "List every active reminder in the current session in creation order, "
        "including its exact id, UTC target, scheduled or overdue state, and "
        "session-local delivery mode."
    ),
    "parameters": {"type": "object", "properties": {}},
}


def tool_schemas() -> list[dict[str, Any]]:
    return [CREATE_SCHEMA, DELETE_SCHEMA, LIST_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name == "schedule_create":
        return schedule_create(
            str(arguments.get("prompt") or ""),
            arguments.get("after_seconds"),
            arguments.get("every_seconds"),
            arguments.get("at"),
            **kwargs,
        )
    if name == "schedule_delete":
        return schedule_delete(str(arguments.get("id") or ""), **kwargs)
    if name == "schedule_list":
        return schedule_list(**kwargs)
    return _error(f"unknown tool: {name}")


def schedule_create(
    prompt: str,
    after_seconds: Any = None,
    every_seconds: Any = None,
    at: Any = None,
    session_id: Optional[str] = None,
) -> str:
    if not prompt.strip():
        return _error("prompt must be a non-empty string")
    selectors = [item for item in (after_seconds, every_seconds, at) if item is not None]
    if len(selectors) != 1:
        return _error("supply exactly one of after_seconds, every_seconds, or at")
    now = time.time()
    try:
        target, kind, interval = _target(now, after_seconds, every_seconds, at)
    except ValueError as exc:
        return _error(str(exc))
    record = {
        "id": uuid.uuid4().hex[:12],
        "prompt": prompt.strip(),
        "kind": kind,
        "everySeconds": interval,
        "targetUtc": datetime.fromtimestamp(target, tz=timezone.utc).isoformat(),
        "targetEpoch": target,
        "state": "scheduled",
        "delivery": "session-local",
        "createdAt": int(now * 1000),
    }
    key = session_id or "default"
    with _LOCK:
        _SCHEDULES.setdefault(key, []).append(record)
    return json.dumps({"success": True, "schedule": _public(record, now)}, ensure_ascii=False)


def schedule_delete(item_id: str, session_id: Optional[str] = None) -> str:
    if not item_id:
        return _error("id must be a non-empty string")
    key = session_id or "default"
    with _LOCK:
        rows = _SCHEDULES.get(key) or []
        kept = [item for item in rows if item["id"] != item_id]
        deleted = len(kept) != len(rows)
        _SCHEDULES[key] = kept
    return json.dumps({"success": True, "deleted": deleted}, ensure_ascii=False)


def schedule_list(session_id: Optional[str] = None) -> str:
    now = time.time()
    key = session_id or "default"
    with _LOCK:
        rows = list(_SCHEDULES.get(key) or [])
    return json.dumps(
        {"success": True, "schedules": [_public(item, now) for item in rows]},
        ensure_ascii=False,
    )


def _target(
    now: float,
    after_seconds: Any,
    every_seconds: Any,
    at: Any,
) -> tuple[float, str, Optional[int]]:
    if after_seconds is not None:
        seconds = _positive_int(after_seconds, "after_seconds")
        return now + seconds, "after_seconds", None
    if every_seconds is not None:
        seconds = _positive_int(every_seconds, "every_seconds")
        if seconds < MIN_EVERY_SECONDS:
            raise ValueError(f"every_seconds must be at least {MIN_EVERY_SECONDS}")
        return now + seconds, "every_seconds", seconds
    if isinstance(at, str):
        instant = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("at string must include a timezone offset")
        return instant.timestamp(), "at", None
    if isinstance(at, dict):
        date = str(at.get("date") or "")
        clock = str(at.get("time") or "")
        zone = str(at.get("time_zone") or "")
        if not date or not clock or not zone:
            raise ValueError("at object requires date, time, and time_zone")
        instant = datetime.fromisoformat(f"{date}T{clock}")
        return instant.timestamp(), "at", None
    raise ValueError("unsupported at value")


def _positive_int(value: Any, name: str) -> int:
    number = int(value)
    if number < 1 or number != value:
        raise ValueError(f"{name} must be a positive safe integer")
    return number


def _public(record: dict[str, Any], now: float) -> dict[str, Any]:
    state = "overdue" if record["targetEpoch"] <= now else "scheduled"
    return {
        "id": record["id"],
        "prompt": record["prompt"],
        "kind": record["kind"],
        "targetUtc": record["targetUtc"],
        "state": state,
        "delivery": record["delivery"],
        **({"everySeconds": record["everySeconds"]} if record["everySeconds"] else {}),
    }


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
