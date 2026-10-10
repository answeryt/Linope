"""Protocols for mailbox requests and the selected channel."""

from __future__ import annotations

from typing import Any, Protocol


class RequestStore(Protocol):
    def submit_request(
        self,
        process_id: str,
        body: dict[str, Any],
        sender_id: str | None = None,
    ) -> str:
        ...

    def take_request(self, process_id: str) -> dict[str, Any] | None:
        ...

    def claim_request(
        self,
        process_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> dict[str, Any] | None:
        ...

    def complete_request(
        self,
        request_id: str,
        reply: dict[str, Any],
        claim_token: str | None = None,
    ) -> None:
        ...

    def release_request(
        self,
        request_id: str,
        claim_token: str | None = None,
    ) -> bool:
        ...

    def lookup_request(self, request_id: str) -> dict[str, Any] | None:
        ...


class ChannelStore(Protocol):
    def selected_channel(self) -> tuple[str | None, dict[str, Any]]:
        ...

    def select_channel(
        self,
        name: str | None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        ...

    def publish_endpoint(
        self,
        process_id: str,
        method: str,
        endpoint: str,
    ) -> None:
        ...

    def endpoint_for(self, process_id: str) -> str | None:
        ...
