"""Load one resource into a capability process."""

from __future__ import annotations

import sys

from kernel.command.command_blocks import tool_body
from kernel.command.parser import USAGE, changes, resource_store_path, take_env_flags
from kernel.command.protocol import CommandSpec
from kernel.process.profile import ProfileUnavailable
from kernel.resource.definition import ResourceKind
from kernel.services import LaunchOptions, ServiceRequest, ServiceSpec, open_service


def parse_load(
    argv: list[str],
) -> tuple[str, tuple, str, str, str, str, tuple[str, ...]]:
    argv, env_file, env_keys = take_env_flags(list(argv))
    rest, store_path = resource_store_path(argv)
    if not rest:
        raise SystemExit(USAGE)
    capability = rest.pop(0)
    change_tokens: list[str] = []
    while len(rest) >= 4 and rest[1:3] == ["change", "-"]:
        change_tokens.extend(rest[:4])
        del rest[:4]
    if len(rest) < 2:
        raise SystemExit("load 的写法是：load 能力名 种类 内容")
    kind = rest.pop(0)
    try:
        ResourceKind(kind)
    except ValueError:
        raise SystemExit(f"不认识的资源种类: {kind}") from None
    return (
        capability,
        changes(change_tokens),
        kind,
        " ".join(rest),
        store_path,
        env_file,
        env_keys,
    )


def run(argv: list[str]) -> int:
    capability, profile_changes, kind, body, store_path, env_file, env_keys = (
        parse_load(argv)
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
        payload = tool_body(body) if kind == "tool" else body
        ticket = service.submit(ServiceRequest(kind=kind, body=payload))
        print(service.wait(ticket, timeout=180))
    finally:
        service.close()
    return 0


SPEC = CommandSpec(name="load", run=run)
