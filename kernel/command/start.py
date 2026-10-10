"""Start capability processes from a profile."""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from typing import Any

from kernel.command.parser import changes, replica_count, take_env_flags
from kernel.command.protocol import CommandSpec
from kernel.environment import HostExecutionPolicy
from kernel.process.profile import Change, ProfileUnavailable
from kernel.resource.store.locator import default_store_locator
from kernel.services import LaunchOptions, ServiceHost, ServiceRequest, ServiceSpec, open_service
from kernel.thread.contracts import ThreadPolicy


def parse_start(
    argv: list[str] | None = None,
) -> tuple[str, tuple[Change, ...], bool, str, int | None, str, tuple[str, ...]]:
    """Split a capability name, flags, changes, and a trailing count."""
    return _parse_start_options(argv)[:7]


def _parse_start_options(
    argv: list[str] | None = None,
) -> tuple[
    str,
    tuple[Change, ...],
    bool,
    str,
    int | None,
    str,
    tuple[str, ...],
    ThreadPolicy,
    str | None,
    float | None,
]:
    """Parse start arguments and retain the historical seven-value API."""
    argv, env_file, env_keys = take_env_flags(list(argv or []))
    parser = start_parser("Run one Capability OS Process")
    parser.add_argument("capability", help="Capability instance id")
    args, rest = parser.parse_known_args(argv)
    count, rest = replica_count(rest)
    return start_options(args.capability, changes(rest), count, args, env_file, env_keys)


def start_parser(description: str) -> argparse.ArgumentParser:
    """The flags ``start`` and ``service start`` share. Positionals are added by the caller."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--resource-store",
        default=default_store_locator(),
        help="Resource Store locator",
    )
    parser.add_argument("--ping", action="store_true", help="Send one ping")
    parser.add_argument(
        "--max-concurrent-tasks",
        type=int,
        default=1,
        help="同时接单的上限，运行中还可以再改",
    )
    parser.add_argument(
        "--min-concurrent-tasks",
        type=int,
        default=1,
        help="同时接单的下限",
    )
    parser.add_argument(
        "--max-sync-workers",
        type=int,
        default=1,
        help="同步工人的上限，运行中还可以再改",
    )
    parser.add_argument("--cwd", default=None, help="这间屋子的工作目录")
    parser.add_argument(
        "--max-runtime-seconds",
        type=float,
        default=None,
        help="墙钟上限，到点后要求进程停下",
    )
    return parser


def start_options(
    head: str,
    parsed_changes: tuple[Change, ...],
    count: int | None,
    args: argparse.Namespace,
    env_file: str,
    env_keys: tuple[str, ...],
) -> tuple:
    """The ten-value option tuple every start-like command hands around."""
    return (
        head,
        parsed_changes,
        args.ping,
        args.resource_store,
        count,
        env_file,
        env_keys,
        ThreadPolicy(
            max_concurrent_tasks=args.max_concurrent_tasks,
            min_concurrent_tasks=args.min_concurrent_tasks,
            max_sync_workers=args.max_sync_workers,
        ),
        args.cwd,
        args.max_runtime_seconds,
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


def run(
    argv: list[str],
    *,
    host: ServiceHost | None = None,
    open_service_fn: Callable[..., Any] | None = None,
) -> int:
    if open_service_fn is None:
        open_service_fn = open_service
    try:
        options = _parse_start_options(argv)
        spec = ServiceSpec(
            kind="capability",
            members=(options[0],),
            changes=options[1],
            replica_count=options[4],
        )
        service = open_service_fn(spec, launch_options(options), host)
    except (ProfileUnavailable, ValueError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1
    serve_until_closed(service, ping=options[2])
    return 0


parse_start_command = parse_start
SPEC = CommandSpec(name="start", run=run)
