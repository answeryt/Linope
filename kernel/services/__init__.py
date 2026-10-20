"""Services name groups of processes. A service does not own their lifetime.

Only the small face is exported. Processes and receipts stay in this package.
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
    "launch_session",
    "service_kinds",
]

_CONTRACTS = {"Member", "Service", "ServiceRequest", "Ticket"}
_SPEC = {"LaunchOptions", "ServiceSpec"}
_HOST = {"ServiceHost", "launch_session"}
_REGISTRY = {"service_kinds"}


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
