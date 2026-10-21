"""Queue and broadcast with nats-py. The subject for one process is ``linope.<pid>``.

A NATS server must already be running. The default address is
``nats://127.0.0.1:4222``.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from kernel.communication.channel import Inbox, needs

DEFAULT_SERVER = "nats://127.0.0.1:4222"
BROADCAST = "linope.all"


class NatsChannel:
    """One connection on its own event loop thread. ``send`` does not wait for a reply."""

    name = "nats"

    def __init__(self, server: str = DEFAULT_SERVER, timeout: float = 5.0) -> None:
        self._nats = needs("nats-py", "nats")
        self._server = server
        self._timeout = float(timeout)
        self._inboxes: dict[str, Inbox] = {}
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="nats-channel", daemon=True)
        self._thread.start()
        self._client = self._run(self._nats.connect(server, connect_timeout=self._timeout))

    def listen(self, me: str) -> str:
        """Subscribe this process to its subject and return the subject."""
        inbox = self._inboxes.setdefault(str(me), Inbox())

        async def take(message: Any) -> None:
            inbox.put(json.loads(message.data.decode("utf-8")))

        subject = f"linope.{me}"
        self._run(self._client.subscribe(subject, cb=take))
        self._run(self._client.subscribe(BROADCAST, cb=take))
        return subject

    def send(self, to: str, message: dict[str, Any], sender: str = "") -> str:
        payload = json.dumps({**message, "sender": sender}, ensure_ascii=False).encode("utf-8")
        self._run(self._client.publish(f"linope.{to}", payload))
        self._run(self._client.flush(timeout=self._timeout))
        return ""

    def broadcast(self, message: dict[str, Any], sender: str = "") -> None:
        """Every process that called ``listen`` sees this one message."""
        payload = json.dumps({**message, "sender": sender}, ensure_ascii=False).encode("utf-8")
        self._run(self._client.publish(BROADCAST, payload))
        self._run(self._client.flush(timeout=self._timeout))

    def receive(self, me: str, after: int = 0) -> list[dict[str, Any]]:
        return self._inboxes.setdefault(str(me), Inbox()).after(after)

    def close(self) -> None:
        try:
            self._run(self._client.drain())
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=1)

    def _run(self, coroutine: Any) -> Any:
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop).result(self._timeout + 1)
