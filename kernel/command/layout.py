"""Replica layout commands."""

from __future__ import annotations

import sys

from kernel.command.parser import USAGE, resource_store_path
from kernel.command.protocol import CommandSpec
from kernel.process.process_manager.replica_layout.registry import (
    layout_names,
    load_layout,
)
from kernel.process.ledger import open_store


def run(argv: list[str]) -> int:
    rest, store_path = resource_store_path(argv)
    if len(rest) != 1:
        raise SystemExit(USAGE)
    name = rest[0]
    store = open_store(store_path)
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


def list_layouts(argv: list[str]) -> int:
    _rest, store_path = resource_store_path(argv)
    store = open_store(store_path)
    try:
        selected, _settings = store.selected_layout()
        for name in layout_names():
            print(f"* {name}" if name == selected else name)
        if selected is None:
            print("????????????")
        return 0
    finally:
        store.close()


SPEC = CommandSpec(name="layout", run=run, aliases=(("layouts", list_layouts),))
