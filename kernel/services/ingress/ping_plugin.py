# -*- coding: utf-8 -*-
"""ASGI health check for the agent worker.

Inject ping (broker.ping) and optionally in_flight. Live and busy are
separate: 204 = live, 500 = broker down, 503 = shutting down with work.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from typing import Any


PLUGIN_NAME = "kernel_ping"
PLUGIN_VERSION = "1.0"

Ping = Callable[..., Any]
Scope = Mapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[Mapping[str, Any]], Awaitable[None]]


async def _call_ping(ping: Ping, timeout: float | None) -> bool:
    result = ping(timeout) if timeout is not None else ping()
    if inspect.isawaitable(result):
        result = await result
    return bool(result)


def make_ping(
    *,
    ping: Ping,
    timeout: float | None = 1.0,
    in_flight: Callable[[], Any] | None = None,
    shutting_down: Callable[[], Any] | None = None,
) -> Callable[..., Awaitable[None]]:
    """Return a raw ASGI HTTP app for GET /ping."""

    async def ping_app(
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope.get("type") != "http":
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return
        status = 204
        if shutting_down is not None and shutting_down():
            busy = in_flight() if in_flight is not None else 0
            if inspect.isawaitable(busy):
                busy = await busy
            if busy:
                status = 503
        elif not await _call_ping(ping, timeout):
            status = 500
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    return ping_app
