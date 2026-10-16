"""Channel selection commands."""

from __future__ import annotations

import sys

from kernel.command.convention import UsageError, guard, parse
from kernel.communication.directory import select_channel
from kernel.communication.registry import channel_names

USAGE = "用法: linope channel use <名称> [地址] | linope channel off"


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    action, rest = argv[0], argv[1:]
    if action == "off":
        return _off(rest)
    if action == "use":
        return _use(rest)
    raise UsageError(USAGE)

def _off(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage="用法: linope channel off")
    if invocation.position:
        raise UsageError("用法: linope channel off")
    select_channel(invocation.store, None, {})
    print("已关闭通道选择，将使用 ledger")
    return 0


def _use(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage="用法: linope channel use <名称> [地址]")
    if not invocation.position or len(invocation.position) > 2:
        raise UsageError("用法: linope channel use <名称> [地址]")
    name = invocation.position[0]
    extra = invocation.position[1:]
    if name not in channel_names():
        known = ", ".join(channel_names())
        print(f"未知通道 {name!r}。已知: {known}", file=sys.stderr)
        return 1
    if name == "nats":
        url = extra[0] if extra else "nats://127.0.0.1:4222"
        settings = {"url": url}
    elif extra:
        raise UsageError("用法: linope channel use <名称> [地址]")
    else:
        settings = {}
    select_channel(invocation.store, name, settings)
    print(f"已选择 {name}")
    return 0
