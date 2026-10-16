"""Ledger mailbox backed by the configured ResourceStore."""

from __future__ import annotations

from typing import Any

from kernel.communication.channel import ChannelOpen
from kernel.communication.ledger_contracts import RequestStore


class LedgerChannel:
    """Point-to-point mailbox backed by process_requests."""

    def __init__(self, opened: ChannelOpen) -> None:
        self._store: RequestStore = opened.store

    def bind(self, process_id: str) -> None:
        del process_id

    def submit(
        self,
        process_id: str,
        body: dict[str, Any],
        sender_id: str | None = None,
    ) -> str:
        return self._store.submit_request(process_id, body, sender_id)

    def take(self, process_id: str) -> dict[str, Any] | None:
        if _mailbox_is_empty(self._store, process_id, claimed_counts=False):
            return None
        return self._store.take_request(process_id)

    def claim(
        self,
        process_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> dict[str, Any] | None:
        """Claim one plain pending request, or one reserved request already placed here."""
        if _mailbox_is_empty(self._store, process_id, claimed_counts=True):
            return None
        return self._store.claim_request(process_id, worker_id, lease_seconds)

    def complete(
        self,
        request_id: str,
        reply: dict[str, Any],
        claim_token: str | None = None,
    ) -> None:
        self._store.complete_request(request_id, reply, claim_token)

    def lookup(self, request_id: str) -> dict[str, Any] | None:
        return self._store.lookup_request(request_id)

    def close(self) -> None:
        return None


def _mailbox_is_empty(store: RequestStore, process_id: str, *, claimed_counts: bool) -> bool:
    """An empty look must not ask the ledger to record anything."""
    counts = getattr(store, "mailbox_counts", None)
    if not callable(counts):
        return False
    pending, claimed = counts(process_id)
    if pending:
        return False
    if claimed_counts and claimed:
        return False
    return True
