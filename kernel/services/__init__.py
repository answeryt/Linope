"""Services: the aggregate boundary of one Agent, made of peer processes.

Only the small face is exported. Processes, receipts, the pool and the
ledger never leave this package.
"""

from __future__ import annotations

__all__ = [
    "LaunchOptions",
    "Member",
    "Service",
    "ServiceHost",
    "ServiceRequest",
    "ServiceSpec",
    "Ticket",
    "open_service",
    "register_service_kind",
    "service_kinds",
]

_CONTRACTS = {"Member", "Service", "ServiceRequest", "Ticket"}
_SPEC = {"LaunchOptions", "ServiceSpec"}
_HOST = {"ServiceHost", "open_service"}
_REGISTRY = {"register_service_kind", "service_kinds"}


def __getattr__(name: str):
    if name in _CONTRACTS:
        from kernel.services import contracts

        return getattr(contracts, name)
    if name in _SPEC:
        from kernel.services import spec

        return getattr(spec, name)
    if name in _HOST:
        from kernel.services import host

        return getattr(host, name)
    if name in _REGISTRY:
        from kernel.services import registry

        return getattr(registry, name)
    raise AttributeError(name)
