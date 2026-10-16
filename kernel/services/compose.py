"""Assemble calls to one service outside the capability plugin.

Same meaning as ``kernel.process.process_manager.compose`` but spoken in
services terms: requests in, tickets out.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from kernel.services.contracts import Service, ServiceRequest, Ticket


def chain(
    service: Service,
    requests: Sequence[ServiceRequest],
    timeout: float = 10.0,
) -> Ticket:
    """Submit in order. Each request carries the previous reply as ``prior``."""
    if not requests:
        raise ValueError("chain 至少要有一次调用")
    ticket: Ticket | None = None
    for request in requests:
        if ticket is not None:
            prior = service.wait(ticket)
            request = replace(request, extras={**request.extras, "prior": prior})
        ticket = service.submit(request, timeout=timeout)
    assert ticket is not None
    return ticket


def group(
    service: Service,
    requests: Sequence[ServiceRequest],
    timeout: float = 10.0,
) -> tuple[Ticket, ...]:
    """Submit every request without waiting for the set to finish."""
    return tuple(service.submit(request, timeout=timeout) for request in requests)


def chord(
    service: Service,
    requests: Sequence[ServiceRequest],
    final: ServiceRequest,
    timeout: float = 10.0,
) -> Ticket:
    """Wait for the group, then submit one request carrying their results."""
    tickets = group(service, requests, timeout)
    results = [service.wait(ticket) for ticket in tickets]
    return service.submit(
        replace(final, extras={**final.extras, "results": results}),
        timeout=timeout,
    )
