"""Load one resource into a capability process."""

from __future__ import annotations

import sys

from kernel.command.command_blocks import tool_body
from kernel.command.convention import Line, UsageError, guard, parse
from kernel.command.parser import parse_changes
from kernel.process.profile import ProfileUnavailable
from kernel.services import LaunchOptions, ServiceRequest, ServiceSpec, launch_session

USAGE = "用法: linope capability load <能力> <种类> <内容>"


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
        payload = tool_body(line.body) if line.kind == "tool" else line.body
        ticket = service.submit(ServiceRequest(kind=line.kind, body=payload))
        print(service.wait(ticket, timeout=180))
    finally:
        service.close()
    return 0


def line_from(argv: list[str]) -> Line:
    invocation = parse(argv, flags={"change": "repeat"}, usage=USAGE)
    if len(invocation.position) < 2:
        raise UsageError(USAGE)
    body = invocation.body if invocation.body is not None else " ".join(invocation.position[2:])
    if not body and invocation.body is None and len(invocation.position) < 3:
        raise UsageError(USAGE)
    return Line(
        name=invocation.position[0],
        kind=invocation.position[1],
        body=body,
        changes=parse_changes(list(invocation.options.get("change") or [])),
        store=invocation.store,
        env_file=invocation.env_file,
        env_keys=invocation.env_keys,
    )


@guard(USAGE)
def run(argv: list[str]) -> int:
    return execute(line_from(argv))
