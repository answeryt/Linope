"""Raise, lower, show, or idle the workers of a running capability."""

from __future__ import annotations

import sys
from typing import Any

from kernel.command.parser import USAGE, resource_store_path
from kernel.command.protocol import CommandSpec
from kernel.load_balancing.hints import Seat
from kernel.load_balancing.process_scale import close_idle
from kernel.load_balancing.workers import lower_ceiling, raise_ceiling
from kernel.process.ledger import open_store


def run(argv: list[str]) -> int:
    rest, store_path = resource_store_path(argv)
    if len(rest) not in {2, 3}:
        raise SystemExit(USAGE)
    verb, capability = rest[0], rest[1]
    if verb not in {"add", "remove", "show", "idle"}:
        raise SystemExit(USAGE)
    if verb in {"show", "idle"} and len(rest) != 2:
        raise SystemExit(USAGE)
    count = 1
    if verb in {"add", "remove"} and len(rest) == 3:
        if not rest[2].isdigit() or int(rest[2]) < 1:
            raise SystemExit("人数至少为 1")
        count = int(rest[2])
    store = open_store(store_path)
    try:
        try:
            if verb == "add":
                ceiling = raise_ceiling(store, capability, count)
                print(f"thread add {capability} {ceiling}")
            elif verb == "remove":
                ceiling = lower_ceiling(store, capability, count)
                print(f"thread remove {capability} {ceiling}")
            elif verb == "show":
                print(_show(store, capability))
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


def _show(store: Any, capability: str) -> str:
    rows = store.running_processes(capability)
    if not rows:
        raise ValueError("这个能力还没有在跑的进程")
    lines: list[str] = []
    for row in rows:
        pending, claimed = store.mailbox_counts(row["process_id"])
        lines.append(
            f"{row['process_id']} pending={pending} claimed={claimed} "
            f"worker_ceiling={_ceiling(row, 'worker_ceiling', 'max_sync_workers')} "
            f"inflight_ceiling={_ceiling(row, 'inflight_ceiling', 'max_concurrent_tasks')}"
        )
    return "\n".join(lines)


def _idle(store: Any, capability: str) -> tuple[str, ...]:
    rows = tuple(store.running_processes(capability))
    if not rows:
        raise ValueError("这个能力还没有在跑的进程")
    found = tuple(_seat(store, capability, row) for row in rows)
    return close_idle(store, found, floor=1)


def _seat(store: Any, capability: str, row: dict[str, Any]) -> Seat:
    pending, claimed = store.mailbox_counts(row["process_id"])
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
        window=None,
        used=0,
        share_mode="",
        handle="",
    )


def _ceiling(row: dict[str, Any], field: str, policy_key: str) -> int:
    if row.get(field) is not None:
        return int(row[field])
    activation = row.get("activation") if isinstance(row.get("activation"), dict) else {}
    policy = activation.get("thread_policy") if isinstance(activation.get("thread_policy"), dict) else {}
    return int(policy.get(policy_key, 1))


SPEC = CommandSpec(name="thread", run=run)
