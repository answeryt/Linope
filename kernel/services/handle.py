"""The runtime face of one service. Implements the four-method contract.

Outside callers get tickets and member views.
"""

from __future__ import annotations

import uuid
from typing import Any

from kernel.services.contracts import Member, ServiceRequest, Ticket
from kernel.services.spec import MemberPlan, ServicePlan

Opened = tuple[tuple[MemberPlan, tuple[Any, ...]], ...]


class ServiceHandle:
    """One opened service."""

    def __init__(
        self,
        plan: ServicePlan,
        opened: Opened,
    ) -> None:
        self._plan = plan
        self._processes: dict[str, tuple[Any, ...]] = {
            member.role: tuple(processes) for member, processes in opened
        }
        self._capabilities: dict[str, str] = {
            member.role: member.capability for member, _processes in opened
        }
        self._receipts: dict[str, tuple[Any, Any]] = {}
        self._closed = False
        self.close_errors: list[str] = []

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

    def processes(self) -> tuple[Any, ...]:
        """The member processes this service opened."""
        found: list[Any] = []
        for group in self._processes.values():
            found.extend(group)
        return tuple(found)

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
                except Exception as exc:
                    self.close_errors.append(f"{_process_id(process)}: {exc}")
        self._receipts.clear()

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
        for process in processes:
            if getattr(process, "is_alive", False):
                return process
        return processes[0]


def _process_id(process: Any) -> str:
    activation = getattr(process, "activation", None)
    return str(getattr(activation, "process_id", "") or "")


def _pid(process: Any) -> int | None:
    pid = getattr(process, "pid", None)
    return None if pid is None else int(pid)
