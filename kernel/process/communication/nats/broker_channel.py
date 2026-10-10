"""NATS request exchange. A running nats-server is required."""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import uuid
from typing import Any

from kernel.process.communication.channel import ChannelOpen


class NatsChannel:
    """Publish to linope.{process_id} and collect the reply from an inbox."""

    def __init__(self, opened: ChannelOpen) -> None:
        self._url = str(opened.settings.get("url") or "nats://127.0.0.1:4222")
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._nc: Any = None
        self._inbox: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._results: dict[str, dict[str, Any]] = {}
        self._reply_to: dict[str, str] = {}
        self._reply_inbox: str | None = None
        self._started = False

    def bind(self, process_id: str) -> None:
        self._ensure()
        subject = f"linope.{process_id}"

        async def subscribe() -> None:
            await self._nc.subscribe(subject, cb=self._on_request)

        _wait(subscribe(), self._loop)

    def submit(
        self,
        process_id: str,
        body: dict[str, Any],
        sender_id: str | None = None,
    ) -> str:
        self._ensure()
        self._ensure_reply_inbox()
        request_id = uuid.uuid4().hex
        with self._lock:
            self._results[request_id] = {"status": "pending", "reply": None}
        payload = json.dumps(
            {
                "request_id": request_id,
                "process_id": process_id,
                "sender_id": sender_id,
                "body": body,
            },
            ensure_ascii=False,
            default=str,
        ).encode()

        async def publish() -> None:
            await self._nc.publish(
                f"linope.{process_id}",
                payload,
                reply=self._reply_inbox,
            )

        _wait(publish(), self._loop)
        return request_id

    def take(self, process_id: str) -> dict[str, Any] | None:
        del process_id
        try:
            return self._inbox.get_nowait()
        except queue.Empty:
            return None

    def claim(
        self,
        process_id: str,
        worker_id: str,
        lease_seconds: float,
    ) -> dict[str, Any] | None:
        del worker_id, lease_seconds
        request = self.take(process_id)
        if request is None:
            return None
        request["claim_token"] = uuid.uuid4().hex
        return request

    def complete(
        self,
        request_id: str,
        reply: dict[str, Any],
        claim_token: str | None = None,
    ) -> None:
        del claim_token
        with self._lock:
            subject = self._reply_to.pop(request_id, None)
        if subject is None or self._nc is None or self._loop is None:
            return
        payload = json.dumps(
            {"request_id": request_id, "reply": reply},
            ensure_ascii=False,
            default=str,
        ).encode()

        async def publish() -> None:
            await self._nc.publish(subject, payload)

        _wait(publish(), self._loop)

    def lookup(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._results.get(request_id)
            if row is None:
                return None
            return {
                "request_id": request_id,
                "status": row["status"],
                "reply": row["reply"],
            }

    def close(self) -> None:
        loop = self._loop
        client = self._nc
        if client is not None and loop is not None:
            async def shutdown() -> None:
                await client.drain()
                await client.close()

            try:
                _wait(shutdown(), loop, timeout=2)
            except Exception:
                pass
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=1)
        self._started = False
        self._nc = None

    def _ensure(self) -> None:
        if self._started:
            return
        nats = _import_nats()
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, name="nats-channel", daemon=True)
        thread.start()
        self._loop = loop
        self._thread = thread

        async def connect():
            return await nats.connect(self._url)

        try:
            self._nc = _wait(connect(), loop, timeout=5)
        except Exception as exc:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=1)
            self._loop = None
            raise RuntimeError(
                f"连接 NATS 失败：{self._url}。请先启动 nats-server。"
            ) from exc
        self._started = True

    def _ensure_reply_inbox(self) -> None:
        if self._reply_inbox is not None:
            return

        async def subscribe() -> str:
            inbox = self._nc.new_inbox()
            await self._nc.subscribe(inbox, cb=self._on_reply)
            return inbox

        self._reply_inbox = _wait(subscribe(), self._loop)

    async def _on_request(self, message: Any) -> None:
        payload = _load(message.data)
        request_id = str(payload.get("request_id") or "")
        if not request_id:
            return
        reply_subject = getattr(message, "reply", None)
        if reply_subject:
            with self._lock:
                self._reply_to[request_id] = str(reply_subject)
        body = payload.get("body")
        self._inbox.put(
            {
                "request_id": request_id,
                "body": body if isinstance(body, dict) else {},
            }
        )

    async def _on_reply(self, message: Any) -> None:
        payload = _load(message.data)
        request_id = str(payload.get("request_id") or "")
        reply = payload.get("reply")
        if not request_id or not isinstance(reply, dict):
            return
        with self._lock:
            self._results[request_id] = {"status": "done", "reply": reply}


def _wait(coro, loop: asyncio.AbstractEventLoop | None, timeout: float = 10):
    if loop is None:
        raise RuntimeError("NATS 通道还没有连接")
    return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=timeout)


def _load(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode())
    except (UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _import_nats():
    try:
        import nats
    except ImportError as exc:
        raise RuntimeError("使用 nats 通道需要先安装：pip install nats-py") from exc
    return nats
