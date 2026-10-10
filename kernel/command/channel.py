"""Channel selection commands."""

from __future__ import annotations

import sys

from kernel.command.parser import USAGE, resource_store_path
from kernel.command.protocol import CommandSpec
from kernel.process.communication.directory import select_channel, selected_channel
from kernel.process.communication.registry import channel_names


def run(argv: list[str]) -> int:
    rest, store_path = resource_store_path(argv)
    if not rest or (rest[0] == "off" and len(rest) != 1):
        raise SystemExit(USAGE)
    if rest == ["off"]:
        select_channel(store_path, None, {})
        print("已关闭通道选择，将使用 ledger")
        return 0
    name = rest[0]
    if name not in channel_names():
        known = ", ".join(channel_names())
        print(f"未知通道 {name!r}。已知: {known}", file=sys.stderr)
        return 1
    if name == "nats":
        if len(rest) > 2:
            raise SystemExit(USAGE)
        url = rest[1] if len(rest) == 2 else "nats://127.0.0.1:4222"
        settings = {"url": url}
    elif len(rest) != 1:
        raise SystemExit(USAGE)
    else:
        settings = {}
    select_channel(store_path, name, settings)
    print(f"已选择 {name}")
    return 0


def list_channels(argv: list[str]) -> int:
    _rest, store_path = resource_store_path(argv)
    selected, _settings = selected_channel(store_path)
    for name in channel_names():
        print(f"* {name}" if name == selected else name)
    if selected is None:
        print("未选择，将使用 ledger")
    return 0


SPEC = CommandSpec(name="channel", run=run, aliases=(("channels", list_channels),))
