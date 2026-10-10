"""The two small contracts of the services layer.

A service is what a caller sees: four methods. A blueprint is what a service
kind supplies: one method. Nothing here holds a live process, a store, a
pool or a receipt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from kernel.services.spec import ServicePlan, ServiceSpec

_FIXED_KEYS = frozenset({"operation", "kind", "body"})


@dataclass(frozen=True)
class ServiceRequest:
    """One request into a service. Serializable; the ingress product."""

    kind: str = ""
    body: Any = None
    role: str = ""
    operation: str = "load"
    extras: dict[str, Any] = field(default_factory=dict)

    def message(self) -> dict[str, Any]:
        """The mailbox message a member process already understands."""
        message: dict[str, Any] = {"operation": self.operation}
        if self.operation == "load":
            message["kind"] = self.kind
            message["body"] = self.body
        elif self.kind:
            message["kind"] = self.kind
        for key, value in self.extras.items():
            if key not in _FIXED_KEYS:
                message[key] = value
        return message

    @classmethod
    def from_message(cls, message: dict[str, Any], role: str = "") -> "ServiceRequest":
        raw = dict(message)
        operation = str(raw.pop("operation", "load") or "load")
        kind = str(raw.pop("kind", "") or "")
        body = raw.pop("body", None)
        return cls(kind=kind, body=body, role=role, operation=operation, extras=raw)


@dataclass(frozen=True)
class Ticket:
    """A receipt for one submitted request. Holds no live object."""

    ticket_id: str
    process_id: str


@dataclass(frozen=True)
class Member:
    """The outside view of one member process."""

    role: str
    capability: str
    process_id: str
    pid: int | None = None
    alive: bool = False


class Service(Protocol):
    """What every service looks like from outside."""

    def submit(self, request: ServiceRequest, *, timeout: float = 10.0) -> Ticket:
        ...

    def wait(self, ticket: Ticket, timeout: float = 10.0) -> dict[str, Any]:
        ...

    def members(self) -> tuple[Member, ...]:
        ...

    def close(self) -> None:
        ...


class ServiceBlueprint(Protocol):
    """How one service kind turns a spec into member declarations."""

    def plan(self, spec: "ServiceSpec") -> "ServicePlan":
        ...
