"""Attach to processes that are already bound to a service.

Closing this handle closes the ledger view. It does not stop a process or
remove a membership.
"""

from __future__ import annotations

import time
from typing import Any

from kernel.services.contracts import Member, ServiceRequest, Ticket
from kernel.services.host import ServiceHost
from kernel.services.spec import LaunchOptions


class BoundService:
    """One named service addressed through its current memberships."""

    def __init__(self, name: str, store: Any) -> None:
        self.name = name
        self._store = store
        self._receipts: dict[str, str] = {}
        self._closed = False
        self._channel: Any = None

    def submit(self, request: ServiceRequest, *, timeout: float = 10.0) -> Ticket:
        del timeout
        if self._closed:
            raise RuntimeError("服务已经关闭")
        role = self._role_for(request)
        process_id = self._pick(role)
        message = request.message()
        message["service_key"] = self.name
        if "lane" not in message:
            message["lane"] = "interactive" if request.kind == "message" else "next"
        if _ledger_selected(self._store):
            request_id = str(self._store.submit_request("", message, None))
            from kernel.services.admit import cycle

            cycle(self._store)
            row = self._store.lookup_request(request_id)
            if row is not None and row.get("status") == "reserved":
                self._store.place_request(request_id, process_id)
            self._receipts[request_id] = process_id
            return Ticket(ticket_id=request_id, process_id=process_id)
        request_id = self._open_channel().submit(process_id, message, None)
        self._receipts[request_id] = process_id
        return Ticket(ticket_id=request_id, process_id=process_id)

    def wait(self, ticket: Ticket, timeout: float | None = None) -> dict[str, Any]:
        del timeout
        if ticket.ticket_id not in self._receipts:
            raise KeyError(f"没有这张回执: {ticket.ticket_id}")
        while True:
            row = self._lookup(ticket.ticket_id)
            if row is None:
                raise KeyError(f"没有这张回执: {ticket.ticket_id}")
            if row.get("status") == "closed":
                raise RuntimeError("这次交互已经过了最晚开始时间")
            if row.get("status") == "done":
                reply = row.get("reply")
                if not isinstance(reply, dict):
                    raise RuntimeError("请求已经结束，但没有回复")
                return reply
            time.sleep(0.02)

    def members(self) -> tuple[Member, ...]:
        return tuple(
            Member(
                role=str(row["role"]),
                capability=str(row.get("capability_id") or ""),
                process_id=str(row["process_id"]),
                pid=None if row.get("pid") is None else int(row["pid"]),
                alive=str(row.get("status") or "") == "running",
            )
            for row in self._store.service_members(self.name)
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        channel = self._channel
        self._channel = None
        if channel is not None:
            try:
                channel.close()
            except Exception:
                pass
        try:
            self._store.close()
        except Exception:
            pass

    def _role_for(self, request: ServiceRequest) -> str:
        roles = tuple(dict.fromkeys(row["role"] for row in self._store.service_members(self.name)))
        if not roles:
            raise RuntimeError(f"服务 {self.name} 还没有绑定进程")
        if request.role:
            if request.role not in roles:
                raise KeyError(f"没有这个关系 {request.role!r}。已有: {', '.join(roles)}")
            return request.role
        if len(roles) == 1:
            return roles[0]
        raise KeyError(f"不知道该交给哪个关系，请点名 role。已有: {', '.join(roles)}")

    def _pick(self, role: str) -> str:
        rows = [
            row
            for row in self._store.service_members(self.name)
            if row["role"] == role and row.get("status") == "running"
        ]
        if not rows:
            raise RuntimeError(f"关系 {role} 没有正在运行的进程")
        if len(rows) == 1:
            return str(rows[0]["process_id"])
        chosen = _choose_id(self._store, rows)
        return chosen or str(rows[0]["process_id"])

    def _open_channel(self) -> Any:
        if self._channel is None:
            from kernel.communication.directory import selected_channel
            from kernel.communication.registry import open_channel

            name, settings = selected_channel(self._store)
            self._channel = open_channel(
                self._store,
                {"name": name or "ledger", "settings": settings},
            )
        return self._channel

    def _lookup(self, request_id: str) -> dict[str, Any] | None:
        if _ledger_selected(self._store):
            return self._store.lookup_request(request_id)
        return self._open_channel().lookup(request_id)


def open_bound(
    name: str,
    options: LaunchOptions | None = None,
    host: ServiceHost | None = None,
) -> BoundService:
    """Open one existing service. The named processes must already be bound."""
    chosen = options or LaunchOptions()
    used = host or ServiceHost()
    store = used.open_store(chosen.store_locator)
    try:
        if store.service_record(name) is None:
            raise KeyError(name)
    except BaseException:
        _close_quietly(store)
        raise
    return BoundService(name, store)


def _ledger_selected(store: Any) -> bool:
    from kernel.communication.directory import selected_channel

    selected, _settings = selected_channel(store)
    return selected in (None, "", "ledger")


def _choose_id(store: Any, rows: list[dict[str, Any]]) -> str | None:
    from kernel.load_balancing.hints import seats
    from kernel.load_balancing.pick import choose

    kind = ""
    identity = {"capability": str(rows[0].get("capability_id") or "")}
    try:
        found = seats(store, kind, identity)
    except Exception:
        return None
    wanted = {str(row["process_id"]) for row in rows}
    candidates = [seat for seat in found if seat.process_id in wanted]
    seat = choose(candidates)
    if seat is None:
        return None
    return str(seat.process_id)


def _close_quietly(store: Any) -> None:
    try:
        store.close()
    except Exception:
        pass
