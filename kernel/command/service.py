"""Group process ids that are already running into one service."""

from __future__ import annotations

import sys
from pathlib import Path

from kernel.command.convention import UsageError, guard
from kernel.services.collection import ServiceGroup

USAGE = "用法: linope service start <进程号> [<进程号> ...]"


def create_service(
    pids: tuple[int, ...],
    *,
    root: Path | None = None,
) -> tuple[ServiceGroup, tuple[str, ...]]:
    """Check the process ledger, then save one service. Nothing is started or stopped."""
    from kernel.process.ledger import ProcessLedger
    from kernel.process.process_manager.liveness import process_matches, reap_dead
    from kernel.process.resource_record import ProcessResourceBook, RecordStatus
    from kernel.services.collection import ServiceBook

    folder = Path.cwd() / ".linope" if root is None else Path(root)
    book = ProcessResourceBook(ProcessLedger(folder / "processes.json"))
    reap_dead(book)
    lines: list[str] = []
    for pid in pids:
        record = book.get(pid)
        if (
            record is None
            or record.status != RecordStatus.READY
            or not process_matches(record.pid, record.started or None)
        ):
            raise ValueError(f"没有这个还开着的进程: {pid}")
        lines.append(f"pid={record.pid} capability={record.capability_id}")
    group = ServiceBook(folder / "services.json").add(pids)
    return group, tuple(lines)


def _pids(argv: list[str]) -> tuple[int, ...]:
    if not argv or argv[0] != "start" or len(argv) < 2:
        raise UsageError(USAGE)
    found: list[int] = []
    for token in argv[1:]:
        if not token.isdigit() or int(token) <= 0:
            raise UsageError(USAGE)
        found.append(int(token))
    if len(found) != len(set(found)):
        raise ValueError("同一个进程号写了两遍")
    return tuple(found)


@guard(USAGE)
def run(argv: list[str]) -> int:
    try:
        pids = _pids(argv)
        group, lines = create_service(pids)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"service={group.service_id}", flush=True)
    for line in lines:
        print(line, flush=True)
    return 0
