"""The one place that wires the ledger, the pool and the reconciler together.

Everything here is a replaceable callable, so tests and other hosts inject
their own without touching the assembler.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from kernel.process.profile import Change
from kernel.services.contracts import Service
from kernel.services.spec import LaunchOptions, ServiceSpec


def _open_store(locator: Any = None) -> Any:
    from kernel.process.ledger import open_store

    return open_store(locator)


def _pool(store: Any) -> Any:
    from kernel.resource.pool import ResourcePool

    return ResourcePool(store)


def _reconciler(pool: Any) -> Any:
    from kernel.process.reconcile import ProcessReconciler

    return ProcessReconciler(pool)


def _load_declaration(capability: str, changes: Sequence[Change]) -> tuple[Any, Any]:
    from kernel.process.profile import load_declaration

    return load_declaration(capability, changes)


@dataclass(frozen=True)
class ServiceHost:
    """Infrastructure a service is assembled on."""

    open_store: Callable[..., Any] = field(default=_open_store)
    pool: Callable[[Any], Any] = field(default=_pool)
    reconciler: Callable[[Any], Any] = field(default=_reconciler)
    load_declaration: Callable[[str, Sequence[Change]], tuple[Any, Any]] = field(
        default=_load_declaration
    )


def open_service(
    spec: ServiceSpec,
    options: LaunchOptions | None = None,
    host: ServiceHost | None = None,
) -> Service:
    """Open one service. This is the only entry callers need."""
    from kernel.services.assembly import ServiceAssembler

    return ServiceAssembler(host or ServiceHost()).open(spec, options or LaunchOptions())
