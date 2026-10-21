"""Remote call with grpcio. One generic method carries the message as JSON bytes.

The directory is named ``grpc_channel`` so it does not hide the ``grpc`` package.
"""

from __future__ import annotations

import json
from concurrent import futures
from typing import Any

from kernel.communication.channel import Inbox, needs

_METHOD = "/linope.Channel/Send"


class GrpcChannel:
    """``addresses`` maps a pid to ``host:port``. ``send`` waits for the receiver's seq."""

    name = "grpc"

    def __init__(self, addresses: dict[str, str] | None = None, timeout: float = 10.0) -> None:
        self._grpc = needs("grpcio", "grpc")
        self._addresses = {str(pid): str(address) for pid, address in (addresses or {}).items()}
        self._timeout = float(timeout)
        self._inboxes: dict[str, Inbox] = {}
        self._servers: list[Any] = []

    def listen(self, me: str, address: str = "127.0.0.1:0") -> str:
        """Serve this process's inbox and return the address others call."""
        grpc = self._grpc
        inbox = self._inboxes.setdefault(str(me), Inbox())

        def take(request: bytes, context: Any) -> bytes:
            del context
            return str(inbox.put(json.loads(request.decode("utf-8")))).encode("utf-8")

        handler = grpc.method_handlers_generic_handler(
            "linope.Channel",
            {"Send": grpc.unary_unary_rpc_method_handler(take)},
        )
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        server.add_generic_rpc_handlers((handler,))
        host = address.rsplit(":", 1)[0]
        port = server.add_insecure_port(address)
        server.start()
        self._servers.append(server)
        bound = f"{host}:{port}"
        self._addresses[str(me)] = bound
        return bound

    def send(self, to: str, message: dict[str, Any], sender: str = "") -> str:
        address = self._addresses.get(str(to))
        if not address:
            raise LookupError(f"不知道进程 {to} 的地址")
        payload = json.dumps({**message, "sender": sender}, ensure_ascii=False).encode("utf-8")
        with self._grpc.insecure_channel(address) as remote:
            call = remote.unary_unary(_METHOD)
            return call(payload, timeout=self._timeout).decode("utf-8")

    def receive(self, me: str, after: int = 0) -> list[dict[str, Any]]:
        return self._inboxes.setdefault(str(me), Inbox()).after(after)

    def close(self) -> None:
        for server in self._servers:
            server.stop(grace=None)
        self._servers.clear()
