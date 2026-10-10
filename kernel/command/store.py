"""Select and inspect the active ResourceStore."""

from __future__ import annotations

import json
from typing import Any

from kernel.command.protocol import CommandSpec
from kernel.resource.store.locator import (
    default_store_locator,
    locator_description,
    set_default_store_locator,
)
from kernel.process.ledger import open_store, store_names


def list_stores(argv: list[str]) -> int:
    if argv:
        raise SystemExit("stores 不接受参数")
    for name in store_names():
        print(name)
    return 0


def run(argv: list[str]) -> int:
    if not argv or argv[0] == "current":
        if len(argv) > 1:
            raise SystemExit("store current 不接受额外参数")
        locator = default_store_locator()
        print(json.dumps(locator_description(locator), ensure_ascii=False))
        return 0

    action = argv[0]
    if action == "use":
        if len(argv) != 2:
            raise SystemExit("store use 的写法是：store use <存储定位信息>")
        try:
            locator = set_default_store_locator(argv[1])
        except ValueError as exc:
            print(exc)
            return 1
        print(f"已选择 {locator}")
        return 0

    if action in {"check", "init", "migrate"}:
        if len(argv) > 2:
            raise SystemExit(f"store {action} 只接受一个存储定位信息")
        locator = argv[1] if len(argv) == 2 else default_store_locator()
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

    raise SystemExit(
        "store 的写法是：store current | store use <定位信息> | "
        "store check [定位信息] | store init [定位信息] | "
        "store migrate [定位信息]"
    )


SPEC = CommandSpec(name="store", run=run, aliases=(("stores", list_stores),))
