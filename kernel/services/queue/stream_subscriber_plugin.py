# -*- coding: utf-8 -*-
"""Pull agent tasks from Redis Stream (consumer group) or an in-memory queue.

Consume is injected (typically usecase.process_task). Redis is imported
inside connect so this file loads without the package installed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_stream_subscriber"
PLUGIN_VERSION = "1.0"

DEFAULT_STREAM = "agent.tasks"
DEFAULT_GROUP = "agent-workers"


class StreamGroupMissing(RuntimeError):
    """Consumer group disappeared while the worker was running."""


async def _call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    result = func(*args, **kwargs)
    if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
        return await result
    return result


def _decode_fields(fields: Mapping[Any, Any]) -> dict[str, Any]:
    raw: Any = None
    for key in (b"data", b"payload", "data", "payload"):
        if key in fields:
            raw = fields[key]
            break
    if raw is None:
        if not fields:
            raise ValueError("empty stream message")
        raw = next(iter(fields.values()))
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"user_message": raw}
    elif isinstance(raw, Mapping):
        payload = dict(raw)
    else:
        payload = {"user_message": str(raw)}
    if not isinstance(payload, dict):
        payload = {"user_message": str(payload)}
    return payload


def _bind_ack(client: Any, stream: str, group: str, message_id: str) -> dict[str, Any]:
    async def ack() -> None:
        await client.xack(stream, group, message_id)

    async def nack() -> None:
        # Leave pending so another consumer can XAUTOCLAIM it.
        return None

    async def reject() -> None:
        await client.xack(stream, group, message_id)

    return {"ack": ack, "nack": nack, "reject": reject}


class MemoryStreamSubscriber:
    """In-process queue used when Redis is not wired yet."""

    def __init__(
        self,
        *,
        consume: Callable[[Mapping[str, Any]], Any],
        logger: logging.Logger | None = None,
    ) -> None:
        if consume is None:
            raise TypeError("consume is required")
        self.consume = consume
        self.logger = logger or logging.getLogger(PLUGIN_NAME)
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.running = False
        self._task: asyncio.Task[None] | None = None

    async def submit(self, task: Mapping[str, Any]) -> None:
        payload = dict(task)
        payload.setdefault("task_id", uuid4().hex)
        acked = asyncio.Event()

        async def ack() -> None:
            acked.set()

        payload["ack"] = ack
        payload["nack"] = ack
        payload["reject"] = ack
        await self._queue.put(payload)

    async def start(self) -> None:
        self.running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self.running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while self.running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            try:
                await _call(self.consume, task)
            except Exception as exc:
                self.logger.exception("memory task failed: %s", exc)


class RedisStreamSubscriber:
    """XREADGROUP worker for agent.tasks."""

    def __init__(
        self,
        *,
        consume: Callable[[Mapping[str, Any]], Any],
        redis_url: str = "redis://localhost:6379/0",
        stream: str = DEFAULT_STREAM,
        group: str = DEFAULT_GROUP,
        consumer: str | None = None,
        block_ms: int = 2000,
        count: int = 1,
        min_idle_ms: int | None = 60_000,
        logger: logging.Logger | None = None,
    ) -> None:
        if consume is None:
            raise TypeError("consume is required")
        self.consume = consume
        self.redis_url = redis_url
        self.stream = stream
        self.group = group
        self.consumer = consumer or f"agent-{os.getpid()}-{uuid4().hex[:8]}"
        self.block_ms = block_ms
        self.count = count
        self.min_idle_ms = min_idle_ms
        self.logger = logger or logging.getLogger(PLUGIN_NAME)
        self.running = False
        self._client: Any = None
        self._task: asyncio.Task[None] | None = None
        self._claim_cursor: bytes = b"0-0"

    async def connect(self) -> Any:
        if self._client is None:
            from redis.asyncio import Redis

            self._client = Redis.from_url(self.redis_url)
        return self._client

    async def ping(self, timeout: float | None = None) -> bool:
        client = await self.connect()
        try:
            if timeout is None:
                return bool(await client.ping())
            return bool(await asyncio.wait_for(client.ping(), timeout=timeout))
        except Exception:
            return False

    async def start(self) -> None:
        client = await self.connect()
        try:
            await client.xgroup_create(
                name=self.stream,
                groupname=self.group,
                id="0",
                mkstream=True,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc) and "already exists" not in str(exc).lower():
                raise
        self.running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self.running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client is not None:
            close = getattr(self._client, "aclose", None) or getattr(self._client, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
                    await result
            self._client = None

    async def _run(self) -> None:
        client = await self.connect()
        while self.running:
            try:
                messages = await self._read(client)
                for message_id, fields in messages:
                    task = _decode_fields(fields)
                    task.setdefault("task_id", message_id)
                    task["message_id"] = message_id
                    task.update(_bind_ack(client, self.stream, self.group, message_id))
                    try:
                        await _call(self.consume, task)
                    except Exception as exc:
                        self.logger.exception("agent task %s failed: %s", message_id, exc)
            except Exception as exc:
                text = str(exc)
                if "NOGROUP" in text:
                    raise StreamGroupMissing(text) from exc
                self.logger.exception("stream fetch error")
                await asyncio.sleep(1)

    async def _read(self, client: Any) -> list[tuple[str, Mapping[Any, Any]]]:
        claimed: list[tuple[str, Mapping[Any, Any]]] = []
        if self.min_idle_ms is not None:
            claimed = await self._autoclaim(client)
            if claimed:
                return claimed
        response = await client.xreadgroup(
            groupname=self.group,
            consumername=self.consumer,
            streams={self.stream: ">"},
            count=self.count,
            block=self.block_ms,
        )
        return _flatten_xread(response)

    async def _autoclaim(self, client: Any) -> list[tuple[str, Mapping[Any, Any]]]:
        result = await client.xautoclaim(
            name=self.stream,
            groupname=self.group,
            consumername=self.consumer,
            min_idle_time=self.min_idle_ms,
            start_id=self._claim_cursor,
            count=self.count,
        )
        next_id, messages, *_ = result
        self._claim_cursor = next_id
        if not messages:
            return []
        out: list[tuple[str, Mapping[Any, Any]]] = []
        for message_id, fields in messages:
            if isinstance(message_id, bytes):
                message_id = message_id.decode("utf-8")
            out.append((str(message_id), fields))
        return out


def _flatten_xread(response: Any) -> list[tuple[str, Mapping[Any, Any]]]:
    out: list[tuple[str, Mapping[Any, Any]]] = []
    if not response:
        return out
    for _stream_name, messages in response:
        for message_id, fields in messages:
            if isinstance(message_id, bytes):
                message_id = message_id.decode("utf-8")
            out.append((str(message_id), fields))
    return out