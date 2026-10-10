"""The runtime face of one service. Implements the four-method contract.

Outside callers get tickets and member views. Processes, receipts, the
store and the pool stay in here. Choosing among several processes of one
role is delegated to ``kernel.load_balancing``; nothing is decided here.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from typing import Any

from kernel.services.contracts import Member, ServiceRequest, Ticket
from kernel.services.spec import MemberPlan, ServicePlan

Opened = Sequence[tuple[MemberPlan, tuple[Any, ...]]]


def _default_seats(store: Any, kind: str, identity: dict[str, Any]) -> Sequence[Any]:
    from kernel.load_balancing.hints import seats

    return seats(store, kind, identity)


def _default_choose(candidates: Sequence[Any]) -> Any | None:
    from kernel.load_balancing.pick import choose

    return choose(candidates)


class ServiceHandle:
    """One opened service."""

    def __init__(
        self,
        plan: ServicePlan,
        opened: Opened,
        store: Any,
        *,
        seats: Callable[[Any, str, dict[str, Any]], Sequence[Any]] | None = None,
        choose: Callable[[Sequence[Any]], Any | None] | None = None,
    ) -> None:
        self._plan = plan
        self._store = store
        self._processes: dict[str, tuple[Any, ...]] = {
            member.role: tuple(processes) for member, processes in opened
        }
        self._capabilities: dict[str, str] = {
            member.role: member.capability for member, _processes in opened
        }
        self._receipts: dict[str, tuple[Any, Any]] = {}
        self._seats = seats or _default_seats
        self._choose = choose or _default_choose
        self._closed = False

    def submit(self, request: ServiceRequest, *, timeout: float = 10.0) -> Ticket:
        if self._closed:
            raise RuntimeError("服务已经关闭")
        role = self._role_for(request)
        process = self._pick(role)
        receipt = process.submit(request.message(), timeout=timeout)
        ticket_id = str(getattr(receipt, "request_id", "") or uuid.uuid4().hex)
        self._receipts[ticket_id] = (process, receipt)
        return Ticket(ticket_id=ticket_id, process_id=_process_id(process))

    def wait(self, ticket: Ticket, timeout: float = 10.0) -> dict[str, Any]:
        try:
            process, receipt = self._receipts[ticket.ticket_id]
        except KeyError:
            raise KeyError(f"没有这张回执: {ticket.ticket_id}") from None
        return process.wait(receipt, timeout=timeout)

    def members(self) -> tuple[Member, ...]:
        found: list[Member] = []
        for role, processes in self._processes.items():
            for process in processes:
                found.append(
                    Member(
                        role=role,
                        capability=self._capabilities[role],
                        process_id=_process_id(process),
                        pid=_pid(process),
                        alive=bool(getattr(process, "is_alive", False)),
                    )
                )
        return tuple(found)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for processes in self._processes.values():
            for process in processes:
                try:
                    process.stop()
                except Exception:
                    pass
        self._receipts.clear()
        try:
            self._store.close()
        except Exception:
            pass

    def _role_for(self, request: ServiceRequest) -> str:
        roles = tuple(self._processes)
        if request.role:
            if request.role not in self._processes:
                raise KeyError(f"没有这个角色 {request.role!r}。已有: {', '.join(roles)}")
            return request.role
        if len(roles) == 1:
            return roles[0]
        role = self._plan.route.get(request.kind)
        if role is None:
            raise KeyError(
                f"不知道 {request.kind!r} 该交给哪个角色，请点名 role。已有: {', '.join(roles)}"
            )
        return role

    def _pick(self, role: str) -> Any:
        processes = self._processes[role]
        if len(processes) == 1:
            return processes[0]
        chosen = self._delegate(processes)
        if chosen is not None:
            return chosen
        for process in processes:
            if getattr(process, "is_alive", False):
                return process
        return processes[0]

    def _delegate(self, processes: tuple[Any, ...]) -> Any | None:
        """Ask the load balancer. Return nothing when it has nothing to say."""
        kind, identity = _resource_of(processes[0])
        if kind is None:
            return None
        try:
            found = self._seats(self._store, kind, identity)
        except Exception:
            return None
        by_id = {_process_id(process): process for process in processes}
        candidates = [seat for seat in found if seat.process_id in by_id]
        seat = self._choose(candidates)
        return None if seat is None else by_id.get(seat.process_id)


def _process_id(process: Any) -> str:
    activation = getattr(process, "activation", None)
    return str(getattr(activation, "process_id", "") or "")


def _pid(process: Any) -> int | None:
    pid = getattr(process, "pid", None)
    return None if pid is None else int(pid)


def _resource_of(process: Any) -> tuple[str | None, dict[str, Any]]:
    grants = getattr(getattr(process, "activation", None), "grants", ()) or ()
    for grant in grants:
        kind = getattr(grant, "kind", None)
        metadata = getattr(grant, "metadata", None) or {}
        identity = metadata.get("identity")
        if kind is not None and isinstance(identity, dict):
            return str(getattr(kind, "value", kind)), dict(identity)
    return None, {}
