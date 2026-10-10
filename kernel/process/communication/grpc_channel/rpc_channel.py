"""gRPC request exchange. One Call carries the same JSON body as the ledger."""

from __future__ import annotations

import json
import queue
import threading
import uuid
from concurrent import futures
from typing import Any

import grpc

from kernel.process.communication.channel import ChannelOpen
from kernel.process.communication.directory import endpoint_for, publish_endpoint
from kernel.process.communication.grpc_channel import process_channel_pb2
from kernel.process.communication.grpc_channel.process_channel_pb2_grpc import (
    ProcessChannelServicer,
    ProcessChannelStub,
    add_ProcessChannelServicer_to_server,
)


class GrpcChannel:
    """Unary Call on 127.0.0.1. submit returns before the reply arrives."""

    def __init__(self, opened: ChannelOpen) -> None:
        self._opened = opened
        self._inbox: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._waiters: dict[str, tuple[threading.Event, dict[str, Any]]] = {}
        self._results: dict[str, dict[str, Any]] = {}
        self._clients: dict[str, grpc.Channel] = {}
        self._server: grpc.Server | None = None

    def bind(self, process_id: str) -> None:
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
        add_ProcessChannelServicer_to_server(
            _Servicer(self._inbox, self._waiters, self._lock),
            server,
        )
        port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        self._server = server
        publish_endpoint(
            self._opened.store_path,
            process_id,
            "grpc",
            f"127.0.0.1:{port}",
        )

    def submit(
        self,
        process_id: str,
        body: dict[str, Any],
        sender_id: str | None = None,
    ) -> str:
        endpoint = endpoint_for(self._opened.store_path, process_id)
        if not endpoint:
            raise RuntimeError(f"还没有进程 {process_id} 的 grpc 地址")
        request_id = uuid.uuid4().hex
        with self._lock:
            self._results[request_id] = {"status": "pending", "reply": None}
        threading.Thread(
            target=self._call,
            args=(endpoint, request_id, process_id, sender_id, body),
            name="grpc-channel",
            daemon=True,
        ).start()
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
            waiter = self._waiters.pop(request_id, None)
        if waiter is None:
            return
        event, holder = waiter
        holder["reply"] = reply
        event.set()

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
        server = self._server
        self._server = None
        if server is not None:
            server.stop(0)
        for channel in self._clients.values():
            channel.close()
        self._clients.clear()

    def _call(
        self,
        endpoint: str,
        request_id: str,
        process_id: str,
        sender_id: str | None,
        body: dict[str, Any],
    ) -> None:
        stub = ProcessChannelStub(self._client(endpoint))
        envelope = process_channel_pb2.Envelope(
            request_id=request_id,
            process_id=process_id,
            sender_id=sender_id or "",
            body=json.dumps(body, ensure_ascii=False, default=str).encode(),
        )
        try:
            reply = stub.Call(envelope, timeout=120)
            parsed = _load(reply.body)
        except Exception as exc:
            parsed = {"event": "error", "error": str(exc)}
        with self._lock:
            self._results[request_id] = {"status": "done", "reply": parsed}

    def _client(self, endpoint: str) -> grpc.Channel:
        channel = self._clients.get(endpoint)
        if channel is None:
            channel = grpc.insecure_channel(endpoint)
            self._clients[endpoint] = channel
        return channel


class _Servicer(ProcessChannelServicer):
    def __init__(
        self,
        inbox: queue.Queue,
        waiters: dict[str, tuple[threading.Event, dict[str, Any]]],
        lock: threading.Lock,
    ) -> None:
        self._inbox = inbox
        self._waiters = waiters
        self._lock = lock

    def Call(self, request, context):
        event = threading.Event()
        holder: dict[str, Any] = {}
        with self._lock:
            self._waiters[request.request_id] = (event, holder)
        self._inbox.put(
            {
                "request_id": request.request_id,
                "body": _load(request.body),
            }
        )
        if not event.wait(120):
            context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "没有收到回复")
        reply = holder.get("reply")
        if not isinstance(reply, dict):
            reply = {}
        return process_channel_pb2.Envelope(
            request_id=request.request_id,
            process_id=request.process_id,
            sender_id=request.sender_id,
            body=json.dumps(reply, ensure_ascii=False, default=str).encode(),
        )


def _load(raw: bytes) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode())
    except (UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
