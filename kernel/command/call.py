"""Call capability operations and compositions."""

from __future__ import annotations

import sys
from dataclasses import replace
from typing import Any

from kernel.command.convention import Invocation, Line, UsageError, parse
from kernel.command.parser import parse_changes
from kernel.process.profile import ProfileUnavailable
from kernel.services import LaunchOptions, ServiceRequest, ServiceSpec, launch_session
from kernel.services.compose import chord, group
from kernel.services.contracts import Ticket

USAGE = "用法: linope capability call|chain|group|chord <能力> <操作>..."


def render(service: Any, line: Line, *, role: str = "") -> str:
    """Run one parsed call and return the text the terminal shows.

    A chain prints every reply. Before each later reply it prints the
    ``prior`` the caller attached. That line is the caller's record, not a
    field the process added to its own reply.
    """
    requests = tuple(
        ServiceRequest(operation=operation, role=role) for operation in line.operations
    )
    if line.mode == "single":
        return str(service.wait(service.submit(requests[0])))
    if line.mode == "chain":
        return _chain_text(service, requests)
    if line.mode == "group":
        return "\n".join(str(service.wait(ticket)) for ticket in group(service, requests))
    assert line.final is not None
    final = chord(service, requests, ServiceRequest(operation=line.final, role=role))
    return str(service.wait(final))


def _chain_text(service: Any, requests: tuple[ServiceRequest, ...], timeout: float = 10.0) -> str:
    lines: list[str] = []
    ticket: Ticket | None = None
    for request in requests:
        if ticket is not None:
            prior = service.wait(ticket)
            lines.append(str(prior))
            lines.append(f"prior={prior}")
            request = replace(request, extras={**request.extras, "prior": prior})
        ticket = service.submit(request, timeout=timeout)
    assert ticket is not None
    lines.append(str(service.wait(ticket)))
    return "\n".join(lines)


def execute(line: Line) -> int:
    try:
        service = launch_session(
            ServiceSpec(kind="capability", members=(line.name,), changes=line.changes),
            LaunchOptions(
                store_locator=line.store,
                env_file=line.env_file,
                env_file_keys=line.env_keys,
            ),
        )
    except (ProfileUnavailable, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1
    try:
        print(render(service, line))
    finally:
        service.close()
    return 0


def run_composition(mode: str, argv: list[str]) -> int:
    """Run one composition. ``mode`` is call, chain, group, or chord."""
    invocation = parse(argv, flags={"change": "repeat"}, usage=USAGE)
    line = _line(mode, invocation)
    return execute(line)


def _line(mode: str, invocation: Invocation) -> Line:
    if not invocation.position:
        raise UsageError(USAGE)
    capability = invocation.position[0]
    operations = invocation.position[1:]
    final = None
    parsed = "single" if mode == "call" else mode
    if parsed == "chord":
        if invocation.body is None:
            raise UsageError("chord 写法是：linope capability chord <能力> <操作>... -- <最后操作>")
        final_parts = invocation.body.split()
        if not operations or len(final_parts) != 1:
            raise UsageError("chord 写法是：linope capability chord <能力> <操作>... -- <最后操作>")
        final = final_parts[0]
    elif parsed == "single":
        if len(operations) != 1:
            raise UsageError("用法: linope capability call <能力> <操作>")
    elif not operations:
        raise UsageError(USAGE)
    return Line(
        name=capability,
        changes=parse_changes(list(invocation.options.get("change") or [])),
        store=invocation.store,
        env_file=invocation.env_file,
        env_keys=invocation.env_keys,
        mode=parsed,
        operations=operations,
        final=final,
    )
