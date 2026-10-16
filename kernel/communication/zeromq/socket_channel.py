"""ZeroMQ request exchange between peer processes."""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from typing import Any

from kernel.communication.channel import ChannelOpen
from kernel.communication.zeromq.registry import (
    endpoint_for,
    publish_endpoint,
    publish_reply,
    remove_endpoint,
    reply_for,
)

REQUEST_RETRY_SECONDS = 0.5
MAX_REQUEST_RETRIES = 10


class ZeroMQChannel:
    """DEALER to ROUTER. Each peer binds its own socket and publishes the port."""

    def __init__(self, opened: ChannelOpen) -> None:
        self._opened = opened
        self._zmq = _import_zmq()
        self._ctx = self._zmq.Context()
        self._commands: queue.Queue = queue.Queue()
        self._inbox: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._results: dict[str, dict[str, Any]] = {}
        self._pending: dict[str, dict[str, Any]] = {}
        self._seen_requests: set[str] = set()
        self._replies: dict[str, dict[str, Any]] = {}
        self._process_id = ""
        self._generation = ""
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="zeromq-channel", daemon=True)
        self._thread.start()

    def bind(self, process_id: str) -> None:
        done = threading.Event()
        box: dict[str, Any] = {}
        self._commands.put(("bind", done, box))
        if not done.wait(5):
            raise TimeoutError("zeromq 没有完成绑定")
        if "error" in box:
            raise box["error"]
        self._process_id = process_id
        self._generation = publish_endpoint(
            self._opened.store_path,
            process_id,
            str(box["endpoint"]),
        )

    def submit(
        self,
        process_id: str,
        body: dict[str, Any],
        sender_id: str | None = None,
    ) -> str:
        endpoint_info = endpoint_for(self._opened.store_path, process_id)
        endpoint = str((endpoint_info or {}).get("endpoint") or "")
        if not endpoint:
            raise RuntimeError(f"还没有进程 {process_id} 的 zeromq 地址")
        request_id = uuid.uuid4().hex
        payload = {
            "kind": "request",
            "request_id": request_id,
            "process_id": process_id,
            "sender_id": sender_id,
            "body": body,
        }
        with self._lock:
            self._results[request_id] = {"status": "pending", "reply": None}
            self._pending[request_id] = {
                "endpoint": endpoint,
                "payload": payload,
                "attempts": 0,
                "last_sent": 0.0,
                "retry_queued": False,
            }
        from kernel.resource.account.recorded import record_communication

        record_communication(self._opened.store, sender_id or process_id, body)
        self._commands.put(("request", request_id))
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
        self._commands.put(("reply", request_id, reply))

    def lookup(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._results.get(request_id)
            if row is None:
                return None
            if row["status"] != "done":
                disk_reply = reply_for(self._opened.store_path, request_id)
                if disk_reply is not None:
                    row = {"status": "done", "reply": disk_reply}
                    self._results[request_id] = row
                    self._pending.pop(request_id, None)
                else:
                    pending = self._pending.get(request_id)
                    if (
                        pending
                        and pending["attempts"] < MAX_REQUEST_RETRIES
                        and not pending["retry_queued"]
                        and time.monotonic() - pending["last_sent"] >= REQUEST_RETRY_SECONDS
                    ):
                        pending["retry_queued"] = True
                        self._commands.put(("retry", request_id))
            return {
                "request_id": request_id,
                "status": row["status"],
                "reply": row["reply"],
            }

    def close(self) -> None:
        self._stop.set()
        self._commands.put(("close",))
        self._thread.join(timeout=1)
        if self._process_id and self._generation:
            remove_endpoint(
                self._opened.store_path,
                self._process_id,
                self._generation,
            )
        try:
            self._ctx.term()
        except Exception:
            pass

    def _run(self) -> None:
        zmq = self._zmq
        poller = zmq.Poller()
        dealers: dict[str, Any] = {}
        identities: dict[str, bytes] = {}
        router_holder: dict[str, Any] = {}
        while not self._stop.is_set():
            self._drain(zmq, poller, dealers, identities, router_holder)
            router = router_holder.get("router")
            if router is None and not dealers:
                time.sleep(0.02)
                continue
            try:
                events = dict(poller.poll(50))
            except zmq.ZMQError:
                if self._stop.is_set():
                    break
                continue
            if router is not None and router in events:
                self._on_router(router, identities)
            for socket in list(dealers.values()):
                if socket in events:
                    self._on_dealer(socket)
            self._drain(zmq, poller, dealers, identities, router_holder)
        router = router_holder.get("router")
        if router is not None:
            router.close(linger=0)
        for socket in dealers.values():
            socket.close(linger=0)

    def _drain(self, zmq, poller, dealers, identities, router_holder) -> None:
        while True:
            try:
                command = self._commands.get_nowait()
            except queue.Empty:
                return
            kind = command[0]
            if kind == "close":
                self._stop.set()
                return
            if kind == "bind":
                _, done, box = command
                try:
                    router_holder["router"] = self._bind_router(zmq, poller, box)
                except Exception as exc:
                    box["error"] = exc
                finally:
                    done.set()
                continue
            if kind == "request":
                _, request_id = command
                with self._lock:
                    pending = dict(self._pending.get(request_id) or {})
                if pending:
                    self._send_request(
                        zmq,
                        poller,
                        dealers,
                        request_id,
                        str(pending["endpoint"]),
                        dict(pending["payload"]),
                    )
                continue
            if kind == "retry":
                _, request_id = command
                with self._lock:
                    pending = dict(self._pending.get(request_id) or {})
                if pending:
                    self._send_request(
                        zmq,
                        poller,
                        dealers,
                        request_id,
                        str(pending["endpoint"]),
                        dict(pending["payload"]),
                        force_reconnect=True,
                    )
                continue
            if kind == "reply":
                _, request_id, reply = command
                self._replies[request_id] = dict(reply)
                publish_reply(self._opened.store_path, request_id, dict(reply))
                router = router_holder.get("router")
                identity = identities.get(request_id)
                if router is None or identity is None:
                    continue
                router.send_multipart(
                    [
                        identity,
                        json.dumps(
                            {"kind": "reply", "request_id": request_id, "reply": reply},
                            ensure_ascii=False,
                            default=str,
                        ).encode(),
                    ]
                )

    def _bind_router(self, zmq, poller, box):
        router = self._ctx.socket(zmq.ROUTER)
        router.setsockopt(zmq.LINGER, 0)
        router.setsockopt(zmq.RCVTIMEO, 200)
        from kernel.resource.store.network import channel_endpoints

        bind_host, advertise = channel_endpoints()
        port = router.bind_to_random_port(f"tcp://{bind_host}")
        poller.register(router, zmq.POLLIN)
        box["endpoint"] = f"tcp://{advertise}:{port}"
        return router

    def _send_request(
        self,
        zmq,
        poller,
        dealers,
        request_id,
        endpoint,
        payload,
        *,
        force_reconnect: bool = False,
    ) -> None:
        if force_reconnect and endpoint in dealers:
            socket = dealers.pop(endpoint)
            try:
                poller.unregister(socket)
            except (KeyError, zmq.ZMQError):
                pass
            socket.close(linger=0)
        socket = dealers.get(endpoint)
        if socket is None:
            socket = self._ctx.socket(zmq.DEALER)
            socket.setsockopt(zmq.LINGER, 0)
            socket.setsockopt(zmq.RCVTIMEO, 200)
            socket.connect(endpoint)
            poller.register(socket, zmq.POLLIN)
            dealers[endpoint] = socket
            socket.send_multipart(
                [
                    json.dumps(
                        {
                            "kind": "hello",
                            "request_id": f"hello-{request_id}",
                        },
                        ensure_ascii=False,
                    ).encode()
                ]
            )
        socket.send_multipart(
            [json.dumps(payload, ensure_ascii=False, default=str).encode()]
        )
        with self._lock:
            pending = self._pending.get(request_id)
            if pending is not None:
                pending["attempts"] += 1
                pending["last_sent"] = time.monotonic()
                pending["retry_queued"] = False

    def _on_router(self, router, identities) -> None:
        try:
            frames = router.recv_multipart()
        except self._zmq.Again:
            return
        if len(frames) < 2:
            return
        message = _load(frames[-1])
        if message.get("kind") == "hello":
            router.send_multipart(
                [
                    frames[0],
                    json.dumps(
                        {
                            "kind": "hello",
                            "request_id": message.get("request_id"),
                            "ready": True,
                        },
                        ensure_ascii=False,
                    ).encode(),
                ]
            )
            return
        if message.get("kind") != "request":
            return
        request_id = str(message.get("request_id") or "")
        if not request_id:
            return
        identities[request_id] = frames[0]
        if request_id in self._replies:
            router.send_multipart(
                [
                    frames[0],
                    json.dumps(
                        {
                            "kind": "reply",
                            "request_id": request_id,
                            "reply": self._replies[request_id],
                        },
                        ensure_ascii=False,
                        default=str,
                    ).encode(),
                ]
            )
            return
        if request_id in self._seen_requests:
            return
        self._seen_requests.add(request_id)
        body = message.get("body")
        self._inbox.put(
            {
                "request_id": request_id,
                "body": body if isinstance(body, dict) else {},
            }
        )

    def _on_dealer(self, socket) -> None:
        try:
            frames = socket.recv_multipart()
        except self._zmq.Again:
            return
        if not frames:
            return
        message = _load(frames[-1])
        if message.get("kind") == "hello":
            return
        if message.get("kind") != "reply":
            return
        request_id = str(message.get("request_id") or "")
        reply = message.get("reply")
        if not request_id or not isinstance(reply, dict):
            return
        with self._lock:
            self._results[request_id] = {"status": "done", "reply": reply}


def _load(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode())
    except (UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _import_zmq():
    try:
        import zmq
    except ImportError as exc:
        raise RuntimeError("使用 zeromq 通道需要先安装：pip install pyzmq") from exc
    return zmq
