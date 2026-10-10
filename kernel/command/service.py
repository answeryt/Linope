"""Start a service of peer processes, or list the registered service kinds."""

from __future__ import annotations

import sys

from kernel.command.parser import changes, member_names, replica_count, take_env_flags
from kernel.command.protocol import CommandSpec
from kernel.command.start import launch_options, serve_until_closed, start_options, start_parser
from kernel.process.profile import ProfileUnavailable
from kernel.services import ServiceSpec, open_service, service_kinds

USAGE = "service 的写法是：service start 种类 [成员能力名...] [主题 change - 值...] [份数]"


def parse_service_start(argv: list[str]) -> tuple[ServiceSpec, tuple]:
    """Split ``<kind> [members...] [changes...] [count]`` plus the start flags."""
    argv, env_file, env_keys = take_env_flags(list(argv))
    parser = start_parser("Run one service made of peer processes")
    parser.add_argument("kind", help="Registered service kind")
    args, rest = parser.parse_known_args(argv)
    members, rest = member_names(rest)
    count, rest = replica_count(rest)
    parsed_changes = changes(rest)
    spec = ServiceSpec(
        kind=args.kind,
        members=members,
        changes=parsed_changes,
        replica_count=count,
    )
    return spec, start_options(args.kind, parsed_changes, count, args, env_file, env_keys)


def run(argv: list[str]) -> int:
    if not argv or argv[0] != "start":
        raise SystemExit(USAGE)
    try:
        spec, options = parse_service_start(argv[1:])
        service = open_service(spec, launch_options(options))
    except (ProfileUnavailable, ValueError, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1
    serve_until_closed(service, ping=options[2])
    return 0


def list_kinds(argv: list[str]) -> int:
    if argv:
        raise SystemExit("services 不带参数")
    for name in service_kinds():
        print(name)
    return 0


SPEC = CommandSpec(name="service", run=run, aliases=(("services", list_kinds),))
