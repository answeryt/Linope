"""One way for peer processes to exchange a business message."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from kernel.process.communication.ledger_contracts import RequestStore


@dataclass
class ChannelOpen:
    """What a channel factory needs. The store stays the resource ledger."""

    store: RequestStore
    store_path: str
    settings: dict[str, Any] = field(default_factory=dict)


class Channel(Protocol):
    """Submit, take, and complete one request. Peers are named by process id."""

    def bind(self, process_id: str) -> None:
        """Start receiving messages addressed to this process."""

    def submit(
        self,
        process_id: str,
        body: dict[str, Any],
        sender_id: str | None = None,
    ) -> str:
        """Hand one message to that process and return a receipt id immediately."""

    def take(self, process_id: str) -> dict[str, Any] | None:
        """Return the next message for this process, or none if it is still waiting."""

    def claim(
        self,
        process_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> dict[str, Any] | None:
        """Atomically reserve one message for an in-process execution unit."""

    def complete(
        self,
        request_id: str,
        reply: dict[str, Any],
        claim_token: str | None = None,
    ) -> None:
        """Store the reply for one receipt."""

    def lookup(self, request_id: str) -> dict[str, Any] | None:
        """Return status and reply for one receipt, when this side can see them."""

    def close(self) -> None:
        """Release sockets or subscriptions this process opened."""
