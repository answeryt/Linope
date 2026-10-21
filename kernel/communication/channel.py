"""How one message reaches another process. The user picks the channel by name.

A message is a plain mapping: ``kind``, ``content``, ``state``, and ``sender``.
``memory`` is the default: it writes the row into the receiver's shared memory,
and the receiver reads every row after the seq it has already seen. ``grpc``,
``nats``, and ``zeromq`` hand the same mapping to the library of that name.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from kernel.communication.address import memory_contents, memory_grant, remember


class Channel(Protocol):
    name: str

    def send(self, to: str, message: dict[str, Any], sender: str = "") -> str:
        """Deliver one message. Returns its seq on the receiving side."""

    def receive(self, me: str, after: int = 0) -> list[dict[str, Any]]:
        """Messages for ``me`` whose seq is after ``after``, oldest first."""

    def close(self) -> None: ...


_FACTORIES: dict[str, Callable[..., Channel]] = {}


def register_channel(name: str, factory: Callable[..., Channel]) -> None:
    _FACTORIES[str(name)] = factory


def channel_names() -> tuple[str, ...]:
    return tuple(sorted(_FACTORIES))


def open_channel(name: str = "memory", **settings: Any) -> Channel:
    """Open the channel the user named. An unknown name lists the known ones."""
    factory = _FACTORIES.get(str(name))
    if factory is None:
        raise ValueError(f"不认识的通道: {name}。可以用: {'、'.join(channel_names())}")
    return factory(**settings)


def needs(package: str, module: str) -> Any:
    """Import a library a channel is built on, or say which package to install."""
    import importlib

    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise RuntimeError(f"这个通道要先安装 {package}: pip install {package}") from exc


class MemoryChannel:
    """Write into the receiver's shared memory. Reading is every row after a seq."""

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
            raise LookupError(f"没有这个还开着的进程: {pid}") from exc
        if memory_grant(grants) is None:
            raise RuntimeError("这个进程没有记忆")
        return grants


class Inbox:
    """Received messages for one process, numbered as they arrive."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self._rows: list[dict[str, Any]] = []

    def put(self, message: dict[str, Any]) -> int:
        with self._lock:
            seq = len(self._rows) + 1
            self._rows.append({**message, "seq": seq})
            return seq

    def after(self, seq: int) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._rows if row["seq"] > int(seq)]


def _register_defaults() -> None:
    from kernel.communication.grpc_channel import GrpcChannel
    from kernel.communication.nats_channel import NatsChannel
    from kernel.communication.zeromq_channel import ZeroMqChannel

    register_channel("memory", MemoryChannel)
    register_channel("grpc", GrpcChannel)
    register_channel("nats", NatsChannel)
    register_channel("zeromq", ZeroMqChannel)


_register_defaults()
