"""Capability commands: one load, or a call composition."""

from __future__ import annotations

from kernel.command.call import run_composition
from kernel.command.convention import UsageError, guard
from kernel.command.load import run as load_run

USAGE = "用法: linope capability load|call|chain|group|chord ..."


@guard(USAGE)
def run(argv: list[str]) -> int:
    if not argv:
        raise UsageError(USAGE)
    action, rest = argv[0], argv[1:]
    if action == "load":
        return load_run(rest)
    if action in {"call", "chain", "group", "chord"}:
        return run_composition(action, rest)
    raise UsageError(USAGE)
