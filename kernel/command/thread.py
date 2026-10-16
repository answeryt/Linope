"""Raise, lower, or idle the workers of a running capability."""

from __future__ import annotations

import sys
from typing import Any

from kernel.command.convention import UsageError, guard, parse
from kernel.load_balancing.hints import Seat
from kernel.load_balancing.process_scale import close_idle
from kernel.load_balancing.workers import lower_ceiling, raise_ceiling
from kernel.process.ledger import open_store

USAGE = "用法: linope process workers add|remove|idle <能力> [--count 人数]"


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv or argv[0] not in {"add", "remove", "idle"}:
        raise UsageError(USAGE)
    verb, rest = argv[0], argv[1:]
    invocation = parse(rest, flags={"count": "int"}, usage=USAGE)
    if len(invocation.position) != 1:
        raise UsageError(USAGE)
    capability = invocation.position[0]
    count = 1 if invocation.options.get("count") is None else int(invocation.options["count"])
    if count < 1:
        raise UsageError("人数至少为 1")
    store = open_store(invocation.store)
    try:
        try:
            if verb == "add":
                ceiling = raise_ceiling(store, capability, count)
                print(f"thread add {capability} {ceiling}")
            elif verb == "remove":
                ceiling = lower_ceiling(store, capability, count)
                print(f"thread remove {capability} {ceiling}")
            else:
                closed = _idle(store, capability)
                shown = " ".join(closed) if closed else "0"
                print(f"thread idle {capability} {shown}")
        except (KeyError, ValueError) as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0
    finally:
        store.close()


def _idle(store: Any, capability: str) -> tuple[str, ...]:
    rows = tuple(store.running_processes(capability))
    if not rows:
        raise ValueError("这个能力还没有在跑的进程")
    found = tuple(_seat(store, capability, row) for row in rows)
    return close_idle(store, found, floor=1)


def _seat(store: Any, capability: str, row: dict[str, Any]) -> Seat:
    pending, claimed = store.mailbox_counts(row["process_id"])
    note = store.note(str(row["process_id"]), "rtt") if hasattr(store, "note") else {}
    return Seat(
        process_id=str(row["process_id"]),
        resource_id="",
        capability_id=capability,
        kind="",
        identity={},
        pending=pending,
        claimed=claimed,
        limits={},
        capacity=1,
        occupied=0,
        window=None,
        share_mode="",
        handle="",
        rtt_ms=int(note.get("ms") or 0),
    )
