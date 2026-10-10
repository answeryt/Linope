"""Shared capability command."""

from __future__ import annotations

from kernel.command.parser import USAGE, resource_store_path
from kernel.command.protocol import CommandSpec
from kernel.process.ledger import open_store


def run(argv: list[str]) -> int:
    rest, store_path = resource_store_path(argv)
    if not rest:
        raise SystemExit(USAGE)
    store = open_store(store_path)
    try:
        if rest == ["off"]:
            store.clear_share()
            print("share off")
            return 0
        store.share_capabilities(tuple(rest))
        print("share " + " ".join(rest))
        return 0
    finally:
        store.close()


SPEC = CommandSpec(name="share", run=run)
