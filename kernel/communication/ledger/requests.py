"""Mailbox requests saved beside the resource ledger."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any


class MailboxSection:
    """Pending, claimed, and finished requests for one process."""

    name = "mailbox"
    flat_keys = ("requests", "request_sequence")

    def __init__(self, lock: threading.RLock) -> None:
        self._lock = lock
        self._requests: dict[str, dict[str, Any]] = {}
        self._request_sequence = 0

    def submit_request(
        self,
        process_id: str,
        body: dict[str, Any],
        sender_id: str | None = None,
    ) -> str:
        with self._lock:
            self._request_sequence += 1
            request_id = str(self._request_sequence)
            schedule = _schedule_from(body)
            self._requests[request_id] = {
                "request_id": request_id,
                "process_id": process_id,
                "sender_id": sender_id,
                "body": dict(body),
                "reply": None,
                "status": "pending",
                "claim_token": None,
                "claimed_by": None,
                "claimed_at": None,
                "claim_expires_at": None,
                **schedule,
            }
            return request_id

    def take_request(self, process_id: str) -> dict[str, Any] | None:
        with self._lock:
            for request in self._requests.values():
                if request["process_id"] != process_id:
                    continue
                if not _claimable(request):
                    continue
                return {
                    "request_id": request["request_id"],
                    "process_id": process_id,
                    "sender_id": request.get("sender_id"),
                    "body": dict(request["body"]),
                }
        return None

    def claim_request(
        self,
        process_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> dict[str, Any] | None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = time.time()
        with self._lock:
            for request in self._requests.values():
                if request["process_id"] != process_id:
                    continue
                if (
                    request["status"] == "claimed"
                    and float(request.get("claim_expires_at") or 0) <= now
                ):
                    _return_claim(request)
                if not _claimable(request):
                    continue
                token = uuid.uuid4().hex
                request.update(
                    status="claimed",
                    claim_token=token,
                    claimed_by=str(worker_id),
                    claimed_at=now,
                    claim_expires_at=now + float(lease_seconds),
                )
                return {
                    "request_id": str(request["request_id"]),
                    "process_id": process_id,
                    "sender_id": request.get("sender_id"),
                    "body": dict(request["body"]),
                    "claim_token": token,
                    "claimed_by": str(worker_id),
                    "claimed_at": now,
                    "claim_expires_at": now + float(lease_seconds),
                }
        return None

    def complete_request(
        self,
        request_id: str,
        reply: dict[str, Any],
        claim_token: str | None = None,
    ) -> None:
        with self._lock:
            request = self._requests[str(request_id)]
            if request["status"] == "done":
                return
            current_token = request.get("claim_token")
            if (
                claim_token is not None
                and current_token is not None
                and claim_token != current_token
            ):
                return
            if request.get("scheduled") and not _depends_done(self, request):
                _requeue(request)
                return
            request["reply"] = dict(reply)
            request["status"] = "done"
            request["claim_token"] = None
            request["claimed_by"] = None
            request["claimed_at"] = None
            request["claim_expires_at"] = None

    def release_request(
        self,
        request_id: str,
        claim_token: str | None = None,
    ) -> bool:
        with self._lock:
            request = self._requests.get(str(request_id))
            if request is None or request["status"] != "claimed":
                return False
            if claim_token is not None and request.get("claim_token") != claim_token:
                return False
            _return_claim(request)
            return True

    def lookup_request(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            request = self._requests.get(str(request_id))
            if request is None:
                return None
            return {
                "request_id": str(request["request_id"]),
                "process_id": request["process_id"],
                "status": request["status"],
                "reply": (
                    dict(request["reply"])
                    if isinstance(request.get("reply"), dict)
                    else None
                ),
            }

    def mailbox_counts(self, process_id: str) -> tuple[int, int]:
        """Pending and claimed requests waiting on one process."""
        with self._lock:
            pending = 0
            claimed = 0
            for request in self._requests.values():
                if request["process_id"] != process_id:
                    continue
                if request["status"] in {"pending", "reserved"}:
                    pending += 1
                elif request["status"] == "claimed":
                    claimed += 1
            return pending, claimed

    def reserve_request(self, request_id: str) -> bool:
        """Hold quota for one recorded request. The process has not taken it."""
        with self._lock:
            request = self._requests.get(str(request_id))
            if request is None or not request.get("scheduled"):
                return False
            if request["status"] != "pending":
                return False
            request["status"] = "reserved"
            return True

    def place_request(self, request_id: str, process_id: str) -> bool:
        """Name the process that may claim one reserved request."""
        with self._lock:
            request = self._requests.get(str(request_id))
            if request is None or request["status"] != "reserved":
                return False
            if not process_id:
                return False
            request["process_id"] = str(process_id)
            return True

    def requeue_request(self, request_id: str) -> bool:
        """Drop a reservation or claim and leave the record waiting."""
        with self._lock:
            request = self._requests.get(str(request_id))
            if request is None or request["status"] in {"done", "closed"}:
                return False
            _requeue(request)
            return True

    def close_request(self, request_id: str) -> bool:
        """Keep an expired interaction recorded without holding quota."""
        with self._lock:
            request = self._requests.get(str(request_id))
            if request is None or request["status"] != "pending":
                return False
            request["status"] = "closed"
            return True

    def admission_rows(self) -> tuple[dict[str, Any], ...]:
        """Scheduling fields of requests that are still open."""
        with self._lock:
            rows: list[dict[str, Any]] = []
            for request in self._requests.values():
                if request["status"] in {"done", "closed"}:
                    continue
                rows.append(_public_schedule(request))
            return tuple(rows)

    def request_schedule(self, request_id: str) -> dict[str, Any] | None:
        """Scheduling fields of one request, including a finished one."""
        with self._lock:
            request = self._requests.get(str(request_id))
            if request is None:
                return None
            return _public_schedule(request)

    def export_part(self) -> dict[str, Any]:
        return {
            "requests": {
                request_id: dict(request)
                for request_id, request in self._requests.items()
            },
            "request_sequence": self._request_sequence,
        }

    def import_part(self, payload: dict[str, Any]) -> None:
        self._requests.clear()
        self._requests.update(
            {
                str(key): dict(value)
                for key, value in (payload.get("requests") or {}).items()
            }
        )
        self._request_sequence = int(payload.get("request_sequence") or 0)


def _schedule_from(body: dict[str, Any]) -> dict[str, Any]:
    lane = _text(body.get("lane"))
    depends_on = _text(body.get("depends_on"))
    service_key = _text(body.get("service_key"))
    start_by = _clock(body.get("start_by"))
    scheduled = any(value is not None for value in (lane, depends_on, service_key, start_by))
    return {
        "lane": lane,
        "depends_on": depends_on,
        "service_key": service_key,
        "start_by": start_by,
        "scheduled": scheduled,
    }


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clock(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _claimable(request: dict[str, Any]) -> bool:
    """Plain requests are claimed in arrival order. Scheduled ones wait for a reservation."""
    if request.get("scheduled"):
        return request["status"] == "reserved" and bool(request.get("process_id"))
    return request["status"] == "pending"


def _return_claim(request: dict[str, Any]) -> None:
    """Put an expired or released claim back where the worker found it."""
    request.update(
        status="reserved" if request.get("scheduled") else "pending",
        claim_token=None,
        claimed_by=None,
        claimed_at=None,
        claim_expires_at=None,
    )


def _requeue(request: dict[str, Any]) -> None:
    request.update(
        status="pending",
        process_id="",
        claim_token=None,
        claimed_by=None,
        claimed_at=None,
        claim_expires_at=None,
    )


def _depends_done(section: MailboxSection, request: dict[str, Any]) -> bool:
    depends_on = request.get("depends_on")
    if not depends_on:
        return True
    parent = section._requests.get(str(depends_on))
    return parent is not None and parent["status"] == "done"


def _public_schedule(request: dict[str, Any]) -> dict[str, Any]:
    body = request.get("body") if isinstance(request.get("body"), dict) else {}
    return {
        "request_id": str(request["request_id"]),
        "process_id": str(request.get("process_id") or ""),
        "status": request["status"],
        "scheduled": bool(request.get("scheduled")),
        "lane": request.get("lane"),
        "depends_on": request.get("depends_on"),
        "service_key": request.get("service_key"),
        "start_by": request.get("start_by"),
        "followed": bool(body.get("followed")),
        "handle": _text(body.get("handle")),
        "href": _text(body.get("href")),
        "relation": _text(body.get("relation")),
        "claim_token": request.get("claim_token"),
    }


def allow_commit(store: Any, request_id: str, *, read: Any = None) -> bool:
    """A scheduled result may be stored only while its dependency, handle, and link still hold."""
    schedule = store.request_schedule(str(request_id))
    if schedule is None or not schedule["scheduled"]:
        return True
    depends_on = schedule.get("depends_on")
    if depends_on:
        parent = store.lookup_request(str(depends_on))
        if parent is None or parent.get("status") != "done":
            return False
    handle = schedule.get("handle")
    authorize = getattr(store, "authorize", None)
    if handle and callable(authorize):
        try:
            authorize(str(handle), str(schedule.get("process_id") or ""))
        except PermissionError:
            return False
    href = schedule.get("href")
    relation = schedule.get("relation")
    if href and relation:
        if read is None:
            return False
        try:
            current = read(str(href))
        except Exception:
            return False
        if not _relation_offered(current, str(relation)):
            return False
    return True


def _relation_offered(current: Any, relation: str) -> bool:
    """True when the current representation still lists this relation."""
    if not isinstance(current, dict):
        return False
    links = current.get("_links")
    if not isinstance(links, dict):
        return False
    link = links.get(relation)
    return isinstance(link, dict) and bool(link.get("href"))
