"""How a process keeps its own notes, and how a caller reaches another service.

``MemoryChannel`` writes one row into a process's memory. A question uses it
for that process's own notes. It is not a way to reach another service.

Another service is reached only through a channel the caller already opened.
``deliver`` names one address. ``publish`` names a topic. Both are plain strings.
The kernel does not choose a transport and does not open one.
"""

from __future__ import annotations

from typing import Any, Protocol

from kernel.communication.address import memory_contents, memory_grant, remember


class Channel(Protocol):
    name: str

    def send(self, to: str, message: dict[str, Any], sender: str = "") -> str:
        """Deliver one message. Returns its seq on the receiving side."""

    def receive(self, me: str, after: int = 0) -> list[dict[str, Any]]:
        """Messages for ``me`` whose seq is after ``after``, oldest first."""

    def close(self) -> None: ...


class ServiceChannel(Protocol):
    """A channel the caller opened. The kernel does not construct one."""

    def send(self, to: str, message: dict[str, Any], sender: str = "") -> str:
        """Deliver one message to one address."""

    def publish(self, topic: str, message: dict[str, Any], sender: str = "") -> None:
        """Deliver one message to a topic. No single recipient is named."""

    def receive(self, me: str, after: int = 0) -> list[dict[str, Any]]:
        """Messages for ``me`` whose seq is after ``after``, oldest first."""

    def close(self) -> None: ...


def deliver(channel: Any, to: str, message: dict[str, Any], sender: str = "") -> str:
    """Hand one message to the address ``to``. The address is the caller's string."""
    _opened(channel)
    return channel.send(str(to), dict(message), sender)


def publish(channel: Any, topic: str, message: dict[str, Any], sender: str = "") -> None:
    """Hand one message to a topic. The topic is the caller's string."""
    _opened(channel)
    channel.publish(str(topic), dict(message), sender)


def _opened(channel: Any) -> None:
    if channel is None:
        raise ValueError("No channel selected")


class MemoryChannel:
    """Write into this process's memory. Reading is every row after a seq."""

    name = "memory"

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    def send(self, to: str, message: dict[str, Any], sender: str = "") -> str:
        grants = self._grants(to)
        kind = str(message.get("kind") or "other")
        content = message.get("content")
        if not isinstance(content, str):
            import json

            content = json.dumps(content, ensure_ascii=False)
        remember(self._pool, grants, kind, content, str(message.get("state") or ""))
        rows = (memory_contents(self._pool, grants) or {}).get("items") or []
        return str(max((int(row.get("seq") or 0) for row in rows), default=0))

    def receive(self, me: str, after: int = 0) -> list[dict[str, Any]]:
        rows = (memory_contents(self._pool, self._grants(me)) or {}).get("items") or []
        return [
            {
                "kind": row.get("kind"),
                "content": row.get("content"),
                "state": row.get("state", ""),
                "seq": int(row.get("seq") or 0),
                "address": row.get("address"),
            }
            for row in sorted(rows, key=lambda row: int(row.get("seq") or 0))
            if int(row.get("seq") or 0) > int(after) and row.get("kind") != "system"
        ]

    def close(self) -> None:
        return None

    def _grants(self, pid: str) -> Any:
        try:
            grants = self._pool.grants_for(int(pid))
        except (KeyError, ValueError) as exc:
            raise LookupError(f"No such open process: {pid}") from exc
        if memory_grant(grants) is None:
            raise RuntimeError("This process has no memory")
        return grants
