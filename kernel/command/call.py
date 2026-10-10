"""Call capability operations and compositions."""

from __future__ import annotations

import sys

from kernel.command.parser import COMPOSITIONS, USAGE, changes, resource_store_path, take_env_flags
from kernel.command.protocol import CommandSpec
from kernel.process.profile import ProfileUnavailable
from kernel.services import LaunchOptions, ServiceRequest, ServiceSpec, open_service
from kernel.services.compose import chain, chord, group


def parse_call(
    argv: list[str],
) -> tuple[str, tuple, str, tuple[str, ...], str | None, str, str, tuple[str, ...]]:
    """Split a capability, changes, composition, and operations."""
    argv, env_file, env_keys = take_env_flags(list(argv))
    rest, store_path = resource_store_path(argv)
    if len(rest) < 2:
        raise SystemExit(USAGE)
    capability = rest.pop(0)
    change_tokens: list[str] = []
    while len(rest) >= 4 and rest[1:3] == ["change", "-"]:
        change_tokens.extend(rest[:4])
        del rest[:4]
    if not rest:
        raise SystemExit(USAGE)
    mode = rest.pop(0)
    parsed_changes = changes(change_tokens)
    if mode == "call":
        raise SystemExit("业务装入请用 linope load")
    if mode not in COMPOSITIONS:
        if rest:
            raise SystemExit("单次调用不接受多个操作；chain/group/chord 可组合调用")
        return (
            capability,
            parsed_changes,
            "single",
            (mode,),
            None,
            store_path,
            env_file,
            env_keys,
        )
    if mode in {"chain", "group"}:
        if not rest or "--" in rest:
            raise SystemExit(f"{mode} 后面要写一个或多个操作")
        return (
            capability,
            parsed_changes,
            mode,
            tuple(rest),
            None,
            store_path,
            env_file,
            env_keys,
        )
    if rest.count("--") != 1:
        raise SystemExit("chord 写法是：chord 操作... -- 最后操作")
    separator = rest.index("--")
    operations = tuple(rest[:separator])
    body = rest[separator + 1 :]
    if not operations or len(body) != 1:
        raise SystemExit("chord 写法是：chord 操作... -- 最后操作")
    return (
        capability,
        parsed_changes,
        mode,
        operations,
        body[0],
        store_path,
        env_file,
        env_keys,
    )


def run(argv: list[str]) -> int:
    capability, profile_changes, mode, operations, body, store_path, env_file, env_keys = (
        parse_call(argv)
    )
    try:
        service = open_service(
            ServiceSpec(kind="capability", members=(capability,), changes=profile_changes),
            LaunchOptions(store_locator=store_path, env_file=env_file, env_file_keys=env_keys),
        )
    except (ProfileUnavailable, KeyError) as exc:
        print(exc, file=sys.stderr)
        return 1
    try:
        requests = tuple(ServiceRequest(operation=operation) for operation in operations)
        if mode == "single":
            print(service.wait(service.submit(requests[0])))
        elif mode == "chain":
            print(service.wait(chain(service, requests)))
        elif mode == "group":
            for ticket in group(service, requests):
                print(service.wait(ticket))
        else:
            assert body is not None
            final = chord(service, requests, ServiceRequest(operation=body))
            print(service.wait(final))
    finally:
        service.close()
    return 0


SPEC = CommandSpec(name="call", run=run)
