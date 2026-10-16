"""Adapters from process communication channels to the thread runtime."""

from __future__ import annotations

import uuid
from typing import Any

from kernel.communication.channel import Channel
from kernel.thread.contracts import ClaimedRequest


class ChannelInbox:
    """Expose atomic channel claiming to an in-process async runtime.

    Older channels only implement ``take``.  They remain usable as a
    single-consumer compatibility path until their backend implements
    ``claim`` explicitly.

    A request that carries a lane, dependency, service, or start time is
    claimable only after admission has reserved it and placement has named
    this process. Plain requests stay first-come.
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
        copied = dict(body) if isinstance(body, dict) else {}
        sender_id = request.get("sender_id")
        if sender_id:
            names = _service_names(self._channel, str(sender_id))
            if len(names) == 1:
                copied["from"] = names[0]
            elif names:
                copied["services"] = list(names)
        return ClaimedRequest(
            request_id=str(request["request_id"]),
            process_id=str(request.get("process_id") or process_id),
            body=copied,
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


def _service_names(channel: Channel, sender_id: str) -> tuple[str, ...]:
    """Services that currently include this sender process."""
    store = getattr(channel, "_store", None)
    lookup = getattr(store, "services_for_process", None)
    if not callable(lookup):
        return ()
    return tuple(str(name) for name in lookup(sender_id))
