"""Which mailbox this process uses, and which outside hosts are listed.

Process-to-process delivery stays in kernel.process.communication.
This door only records the channel name and the outbound list.
An empty outbound list is not enforced yet, so model calls keep their exit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CommunicationDoor:
    channel_name: str = "ledger"
    channel_settings: dict[str, Any] = field(default_factory=dict)
    outbound_hosts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.channel_name.strip():
            raise ValueError("通道名字不能是空白")

    def allows_outbound(self, host: str) -> bool:
        """Empty list means this round does not block the existing exit."""
        if not self.outbound_hosts:
            return True
        return host in self.outbound_hosts

    def payload(self) -> dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "channel_settings": dict(self.channel_settings),
            "outbound_hosts": list(self.outbound_hosts),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "CommunicationDoor":
        raw = dict(payload or {})
        settings = raw.get("channel_settings") or {}
        hosts = raw.get("outbound_hosts") or ()
        return cls(
            channel_name=str(raw.get("channel_name") or "ledger"),
            channel_settings=dict(settings),
            outbound_hosts=tuple(str(host) for host in hosts),
        )

    @classmethod
    def from_parts(
        cls,
        *,
        channel_name: str,
        channel_settings: dict[str, Any] | None,
        grants: tuple[object, ...] = (),
        outbound_hosts: tuple[str, ...] = (),
    ) -> "CommunicationDoor":
        hosts = outbound_hosts or _hosts_from_grants(grants)
        return cls(
            channel_name=channel_name or "ledger",
            channel_settings=dict(channel_settings or {}),
            outbound_hosts=hosts,
        )


def _hosts_from_grants(grants: tuple[object, ...]) -> tuple[str, ...]:
    found: list[str] = []
    for grant in grants:
        kind = getattr(grant, "kind", "")
        if str(getattr(kind, "value", kind)) != "network":
            continue
        metadata = getattr(grant, "metadata", {}) or {}
        hosts = metadata.get("hosts") if isinstance(metadata, dict) else None
        if isinstance(hosts, (list, tuple)):
            found.extend(str(host) for host in hosts if str(host).strip())
    return tuple(found)
