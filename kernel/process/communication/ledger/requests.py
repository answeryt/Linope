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
            }
            return request_id

    def take_request(self, process_id: str) -> dict[str, Any] | None:
        with self._lock:
            for request in self._requests.values():
                if (
                    request["process_id"] == process_id
                    and request["status"] == "pending"
                ):
                    return {
                        "request_id": request["request_id"],
                        "process_id": process_id,
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
                    request.update(
                        status="pending",
                        claim_token=None,
                        claimed_by=None,
                        claimed_at=None,
                        claim_expires_at=None,
                    )
                if request["status"] != "pending":
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
            request.update(
                status="pending",
                claim_token=None,
                claimed_by=None,
                claimed_at=None,
                claim_expires_at=None,
            )
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
                if request["status"] == "pending":
                    pending += 1
                elif request["status"] == "claimed":
                    claimed += 1
            return pending, claimed

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
