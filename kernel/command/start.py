"""Start one capability process and the options every launch shares."""

from __future__ import annotations

import sys
import time
from typing import Any

from kernel.command.convention import Invocation, UsageError, guard, parse
from kernel.command.parser import optional_count, parse_changes
from kernel.environment import HostExecutionPolicy
from kernel.process.profile import Change, ProfileUnavailable
from kernel.services import LaunchOptions, ServiceRequest, ServiceSpec, launch_session
from kernel.thread.contracts import ThreadPolicy

START_FLAGS = {
    "ping": "bool",
    "change": "repeat",
    "count": "int",
    "cwd": "str",
    "max-runtime-seconds": "float",
    "max-concurrent-tasks": "int",
    "min-concurrent-tasks": "int",
    "max-sync-workers": "int",
}
START_USAGE = "用法: linope process start <能力> [--change 主题=值] [--count 份数] [--ping]"


def parse_start(argv: list[str] | None = None) -> tuple:
    """Return the historical option prefix used by process tests."""
    return _options(parse(list(argv or []), flags=START_FLAGS, usage=START_USAGE))[:7]


def _parse_start_options(argv: list[str] | None = None) -> tuple:
    """Parse one process start, including the thread and room options."""
    return _options(parse(list(argv or []), flags=START_FLAGS, usage=START_USAGE))


def _options(invocation: Invocation) -> tuple:
    if len(invocation.position) != 1:
        raise UsageError(START_USAGE)
    changes = parse_changes(list(invocation.options.get("change") or []))
    count = optional_count(invocation.options.get("count"))
    runtime = invocation.options.get("max-runtime-seconds")
    return (
        invocation.position[0],
        changes,
        bool(invocation.options.get("ping")),
        invocation.store,
        count,
        invocation.env_file,
        invocation.env_keys,
        ThreadPolicy(
            max_concurrent_tasks=int(invocation.options.get("max-concurrent-tasks") or 1),
            min_concurrent_tasks=int(invocation.options.get("min-concurrent-tasks") or 1),
            max_sync_workers=int(invocation.options.get("max-sync-workers") or 1),
        ),
        invocation.options.get("cwd"),
        runtime,
    )


def options_for(
    *,
    capability: str,
    changes: tuple[Change, ...] = (),
    ping: bool = False,
    store: str,
    count: int | None = None,
    env_file: str = "",
    env_keys: tuple[str, ...] = (),
    cwd: str | None = None,
    max_runtime_seconds: float | None = None,
) -> tuple:
    """Build the ten-value option tuple from an already saved definition."""
    return (
        capability,
        changes,
        ping,
        store,
        count,
        env_file,
        env_keys,
        ThreadPolicy(),
        cwd,
        max_runtime_seconds,
    )


def launch_options(options: tuple) -> LaunchOptions:
    """Turn parsed start options into the room and policies of a service."""
    (
        _capability,
        _changes,
        _ping,
        store_path,
        _count,
        env_file,
        env_keys,
        thread_policy,
        cwd,
        max_runtime_seconds,
    ) = options
    return LaunchOptions(
        store_locator=store_path,
        thread_policy=thread_policy,
        host_policy=(
            HostExecutionPolicy(max_runtime_seconds=max_runtime_seconds)
            if max_runtime_seconds is not None
            else None
        ),
        env_file=env_file,
        env_file_keys=env_keys,
        cwd=cwd,
    )


def member_lines(service: Any) -> list[str]:
    """One line per member, the same shape the command always printed."""
    return [
        f"process_id={member.process_id} pid={member.pid} capability={member.capability}"
        for member in service.members()
    ]


def serve_until_closed(service: Any, *, ping: bool) -> None:
    """Print, optionally ping, then stay until every member has left."""
    for line in member_lines(service):
        print(line)
    try:
        if ping:
            for role in dict.fromkeys(member.role for member in service.members()):
                ticket = service.submit(ServiceRequest(operation="ping", role=role))
                print(service.wait(ticket))
        while any(member.alive for member in service.members()):
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        service.close()


def launch_capability(options: tuple) -> int:
    """Open one capability service and hold it until it stops."""
    try:
        service = launch_session(
            ServiceSpec(
                kind="capability",
                members=(options[0],),
                changes=options[1],
                replica_count=options[4],
            ),
            launch_options(options),
        )
    except (ProfileUnavailable, ValueError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1
    serve_until_closed(service, ping=options[2])
    return 0


@guard(START_USAGE)
def run(argv: list[str]) -> int:
    return launch_capability(_parse_start_options(argv))
