"""Start one capability process and the options every launch shares."""

from __future__ import annotations

import sys
from typing import Any

from kernel.command.convention import Invocation, UsageError, guard, parse
from kernel.command.process.listen import hold
from kernel.command.parser import optional_count, parse_changes
from kernel.environment import HostExecutionPolicy
from kernel.process.profile import Change, ProfileUnavailable
from kernel.services import LaunchOptions, ServiceSpec, launch_session
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
    "share": "repeat",
    "once": "bool",
    "with": "repeat",
}
START_USAGE = (
    "用法: linope process start <能力> [--change 主题=值] [--count 份数] "
    "[--share 资源种类] [--with 种类=身份] [--once] [--ping]"
)


def parse_start(argv: list[str] | None = None) -> tuple:
    """Return the option prefix used by process tests."""
    return _options(parse(list(argv or []), flags=START_FLAGS, usage=START_USAGE))[:6]


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
        tuple(invocation.options.get("share") or ()),
        bool(invocation.options.get("once")),
        tuple(invocation.options.get("with") or ()),
    )


def options_for(
    *,
    capability: str,
    changes: tuple[Change, ...] = (),
    ping: bool = False,
    count: int | None = None,
    env_file: str = "",
    env_keys: tuple[str, ...] = (),
    cwd: str | None = None,
    max_runtime_seconds: float | None = None,
) -> tuple:
    """Build the option tuple from an already saved definition."""
    return (
        capability,
        changes,
        ping,
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
        _count,
        env_file,
        env_keys,
        thread_policy,
        cwd,
        max_runtime_seconds,
        *rest,
    ) = options
    shared = tuple(rest[0]) if rest else ()
    once = bool(rest[1]) if len(rest) > 1 else False
    chosen = tuple(rest[2]) if len(rest) > 2 else ()
    return LaunchOptions(
        thread_policy=thread_policy,
        host_policy=(
            HostExecutionPolicy(max_runtime_seconds=max_runtime_seconds)
            if max_runtime_seconds is not None
            else None
        ),
        env_file=env_file,
        env_file_keys=env_keys,
        cwd=cwd,
        shared=shared,
        once=once,
        chosen=chosen,
    )


def member_lines(service: Any) -> list[str]:
    """One line per member, the same shape the command always printed."""
    return [
        f"process_id={member.process_id} pid={member.pid} capability={member.capability}"
        for member in service.members()
    ]


def serve_until_closed(service: Any, *, ping: bool) -> bool:
    """Print, optionally ping, then stay until every member has left."""
    return hold(service, ping=ping, once=False)


def launch_capability(options: tuple) -> int:
    """Open one capability service and hold it until it stops."""
    try:
        service = launch_session(
            ServiceSpec(
                kind="capability",
                members=(options[0],),
                changes=options[1],
                replica_count=options[3],
            ),
            launch_options(options),
        )
    except (ProfileUnavailable, ValueError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1
    once = len(options) > 10 and bool(options[10])
    return 0 if hold(service, ping=bool(options[2]), once=once) else 1


@guard(START_USAGE)
def run(argv: list[str]) -> int:
    return launch_capability(_parse_start_options(argv))
