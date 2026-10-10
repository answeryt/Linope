"""Register channels by name. Callers ask for a name and receive the interface."""

from __future__ import annotations

from typing import Any, Callable

from kernel.process.communication.channel import Channel, ChannelOpen

_RESERVED = "off"
_BUILTINS = frozenset({"ledger", "zeromq", "grpc", "nats"})
_registry: dict[str, Callable[[ChannelOpen], Channel]] = {}


def register_channel(name: str, factory: Callable[[ChannelOpen], Channel]) -> None:
    """Remember one channel factory under a name. `off` is reserved."""
    if name == _RESERVED:
        raise ValueError("off 是保留名，不能登记成一种通道")
    if not name or name.strip() != name or not name.strip():
        raise ValueError("通道名不能为空")
    _registry[name] = factory


def unregister_channel(name: str) -> None:
    """Drop a custom channel. Built-in names stay registered."""
    if name in _BUILTINS:
        raise ValueError("内置通道不能取消登记")
    _registry.pop(name, None)


def load_channel(name: str, opened: ChannelOpen) -> Channel:
    """Build the channel registered under this name."""
    try:
        factory = _registry[name]
    except KeyError:
        known = ", ".join(sorted(_registry))
        raise KeyError(f"未知通道 {name!r}。已知: {known}") from None
    return factory(opened)


def open_channel(store: Any, choice: dict[str, Any] | None) -> Channel:
    """Open the channel named in a startup package. Missing means the ledger."""
    raw = choice or {}
    name = str(raw.get("name") or "ledger")
    settings = raw.get("settings")
    if not isinstance(settings, dict):
        settings = {}
    opened = ChannelOpen(
        store=store,
        store_path=str(
            getattr(store, "locator", getattr(store, "path", ""))
        ),
        settings=dict(settings),
    )
    return load_channel(name, opened)


def channel_names() -> tuple[str, ...]:
    return tuple(sorted(_registry))


def _zeromq(opened: ChannelOpen) -> Channel:
    try:
        from kernel.process.communication.zeromq.socket_channel import ZeroMQChannel
    except ImportError as exc:
        raise RuntimeError("使用 zeromq 通道需要先安装：pip install pyzmq") from exc
    return ZeroMQChannel(opened)


def _grpc(opened: ChannelOpen) -> Channel:
    try:
        from kernel.process.communication.grpc_channel.rpc_channel import GrpcChannel
    except ImportError as exc:
        raise RuntimeError("使用 grpc 通道需要先安装：pip install grpcio") from exc
    return GrpcChannel(opened)


def _nats(opened: ChannelOpen) -> Channel:
    try:
        from kernel.process.communication.nats.broker_channel import NatsChannel
    except ImportError as exc:
        raise RuntimeError("使用 nats 通道需要先安装：pip install nats-py") from exc
    return NatsChannel(opened)


def _register_builtins() -> None:
    if _BUILTINS.issubset(_registry):
        return
    from kernel.process.communication.ledger.mailbox import LedgerChannel

    register_channel("ledger", lambda opened: LedgerChannel(opened))
    register_channel("zeromq", _zeromq)
    register_channel("grpc", _grpc)
    register_channel("nats", _nats)


_register_builtins()
