"""Replica layout commands."""

from __future__ import annotations

import sys

from kernel.command.convention import UsageError, guard, parse
from kernel.process.process_manager.replica_layout.registry import load_layout
from kernel.process.ledger import open_store

USAGE = "用法: linope layout use <名称> | linope layout off"


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    action, rest = argv[0], argv[1:]
    if action == "off":
        return _select(["off", *rest])
    if action == "use":
        return _select(rest)
    raise UsageError(USAGE)


def _select(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage=USAGE)
    if len(invocation.position) != 1:
        raise UsageError(USAGE)
    name = invocation.position[0]
    store = open_store(invocation.store)
    try:
        if name == "off":
            store.select_layout(None, {})
            print("已关闭副本布局")
            return 0
        try:
            layout = load_layout(name)
        except KeyError as exc:
            print(exc, file=sys.stderr)
            return 1
        defaults = getattr(layout, "default_settings", None)
        settings = defaults() if defaults is not None else {}
        store.select_layout(name, settings)
        print(f"已选择布局 {name}")
        return 0
    finally:
        store.close()
