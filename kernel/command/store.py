"""Select and inspect the active ResourceStore."""

from __future__ import annotations

import json
from typing import Any

from kernel.command.convention import UsageError, guard, parse
from kernel.process.ledger import open_store
from kernel.resource.store.locator import (
    default_store_locator,
    locator_description,
    set_default_store_locator,
)

USAGE = (
    "用法: linope store current | linope store use <定位串> | "
    "linope store check [定位串] | linope store init [定位串] | linope store migrate [定位串]"
)


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    action, rest = argv[0], argv[1:]
    if action == "current":
        return _current(rest)
    if action == "use":
        return _use(rest)
    if action in {"check", "init", "migrate"}:
        return _operate(action, rest)
    raise UsageError(USAGE)

def _current(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage="用法: linope store current")
    if invocation.position:
        raise UsageError("用法: linope store current")
    print(json.dumps(locator_description(default_store_locator()), ensure_ascii=False))
    return 0


def _use(argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage="用法: linope store use <定位串>")
    if len(invocation.position) != 1:
        raise UsageError("用法: linope store use <定位串>")
    try:
        locator = set_default_store_locator(invocation.position[0])
    except ValueError as exc:
        print(exc)
        return 1
    print(f"已选择 {locator}")
    return 0


def _operate(action: str, argv: list[str]) -> int:
    invocation = parse(argv, flags={}, usage=f"用法: linope store {action} [定位串]")
    if len(invocation.position) > 1:
        raise UsageError(f"用法: linope store {action} [定位串]")
    locator = invocation.position[0] if invocation.position else default_store_locator()
    store = open_store(locator, reap=False)
    try:
        if action == "check":
            result: dict[str, Any] = store.check()
            print(json.dumps(result, ensure_ascii=False, default=str))
        elif action == "init":
            store.initialize_schema()
            print(f"已初始化 {store.locator}")
        else:
            store.migrate()
            print(f"已迁移 {store.locator}")
    finally:
        store.close()
    return 0
