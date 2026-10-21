"""Point to point with pyzmq. Each process binds a PULL socket at its own address."""

from __future__ import annotations

import json
import threading
from typing import Any

from kernel.communication.channel import Inbox, needs


class ZeroMqChannel:
    """``addresses`` maps a pid to ``tcp://host:port``. ``send`` does not wait for a reply."""

    name = "zeromq"

    def __init__(self, addresses: dict[str, str] | None = None) -> None:
        self._zmq = needs("pyzmq", "zmq")
        self._context = self._zmq.Context.instance()
        self._addresses = {str(pid): str(address) for pid, address in (addresses or {}).items()}
        self._inboxes: dict[str, Inbox] = {}
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()

    def listen(self, me: str, address: str = "tcp://127.0.0.1:*") -> str:
        """Bind this process's socket and return the address others send to."""
        socket = self._context.socket(self._zmq.PULL)
        socket.bind(address)
        bound = socket.getsockopt_string(self._zmq.LAST_ENDPOINT)
        self._addresses[str(me)] = bound
        inbox = self._inboxes.setdefault(str(me), Inbox())
        thread = threading.Thread(target=self._drain, args=(socket, inbox), daemon=True)
        thread.start()
        self._threads.append(thread)
        return bound

    def send(self, to: str, message: dict[str, Any], sender: str = "") -> str:
        address = self._addresses.get(str(to))
        if not address:
            raise LookupError(f"不知道进程 {to} 的地址")
        socket = self._context.socket(self._zmq.PUSH)
        try:
            socket.connect(address)
            socket.send_string(json.dumps({**message, "sender": sender}, ensure_ascii=False))
        finally:
            socket.close(linger=1000)
        return ""

    def receive(self, me: str, after: int = 0) -> list[dict[str, Any]]:
        return self._inboxes.setdefault(str(me), Inbox()).after(after)

    def close(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=1)

    def _drain(self, socket: Any, inbox: Inbox) -> None:
        poller = self._zmq.Poller()
        poller.register(socket, self._zmq.POLLIN)
        try:
            while not self._stop.is_set():
                if dict(poller.poll(100)).get(socket):
                    inbox.put(json.loads(socket.recv_string()))
        finally:
            socket.close(linger=0)
