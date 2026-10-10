"""Adapters from process communication channels to the thread runtime."""

from __future__ import annotations

import uuid
from typing import Any

from kernel.process.communication.channel import Channel
from kernel.thread.contracts import ClaimedRequest


class ChannelInbox:
    """Expose atomic channel claiming to an in-process async runtime.

    Older channels only implement ``take``.  They remain usable as a
    single-consumer compatibility path until their backend implements
    ``claim`` explicitly.
    """

    def __init__(self, channel: Channel) -> None:
        self._channel = channel

    def claim(
        self,
        process_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> ClaimedRequest | None:
        claim = getattr(self._channel, "claim", None)
        if callable(claim):
            request = claim(process_id, worker_id, lease_seconds)
        else:
            request = self._channel.take(process_id)
        if request is None:
            return None
        body = request.get("body")
        return ClaimedRequest(
            request_id=str(request["request_id"]),
            process_id=str(request.get("process_id") or process_id),
            body=dict(body) if isinstance(body, dict) else {},
            claim_token=str(request.get("claim_token") or uuid.uuid4().hex),
            worker_id=worker_id,
        )

    def complete(
        self,
        request_id: str,
        reply: dict[str, Any],
        claim_token: str | None = None,
    ) -> None:
        complete = self._channel.complete
        if claim_token is None:
            complete(request_id, reply)
            return
        try:
            complete(request_id, reply, claim_token=claim_token)
        except TypeError:
            complete(request_id, reply)

    def lookup(self, request_id: str) -> dict[str, Any] | None:
        return self._channel.lookup(request_id)
