"""Group process ids that are already running into one service, and talk to it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kernel.command.convention import UsageError, guard
from kernel.services.collection import ServiceGroup

USAGE = "usage: linope service start <pid> [<pid> ...]"
LOAD_USAGE = "usage: service load <service id> -- <body>"


def create_service(
    pids: tuple[int, ...],
    *,
    root: Path | None = None,
) -> tuple[ServiceGroup, tuple[dict[str, Any], ...]]:
    """Check the process ledger, then save one service. Nothing is started or stopped."""
    from kernel.process.ledger import ProcessLedger
    from kernel.process.process_manager.liveness import process_matches, reap_dead
    from kernel.process.resource_record import ProcessResourceBook, RecordStatus
    from kernel.services.collection import ServiceBook

    folder = _folder(root)
    book = ProcessResourceBook(ProcessLedger(folder / "processes.json"))
    reap_dead(book)
    lines: list[dict[str, Any]] = []
    for pid in pids:
        record = book.get(pid)
        if (
            record is None
            or record.status != RecordStatus.READY
            or not process_matches(record.pid, record.started or None)
        ):
            raise ValueError(f"No such open process: {pid}")
        lines.append({"pid": record.pid, "capability": record.capability_id})
    group = ServiceBook(folder / "services.json").add(pids)
    return group, tuple(lines)


def entry_of(group: ServiceGroup, processes: Any) -> int:
    """Return a living service member without assigning it a model role."""
    from kernel.command.process.listen import _pid_of

    members = set(group.pids)
    living = sorted(
        (
            _pid_of(process)
            for process in processes
            if getattr(process, "is_alive", False) and _pid_of(process) in members
        ),
    )
    if living:
        return living[0]
    raise ValueError("This service has no open process")


def accept(runtime: Any, service_id: int, body: str, *, root: Path | None = None) -> str:
    """Hand words that already arrived to this service's one model, as ``load message``.

    The channel that carried the words stays with the caller. This records them
    in the entry process's own memory through the usual load path.
    """
    from kernel.command.process.listen import PING_TIMEOUT, _one_line, _processes
    from kernel.services.collection import ServiceBook

    if runtime is None:
        raise ValueError("No kernel runtime")
    try:
        number = int(service_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"No such service: {service_id}") from exc
    if number <= 0:
        raise ValueError(f"No such service: {service_id}")
    group = ServiceBook(_folder(root) / "services.json").get(number)
    if group is None:
        raise ValueError(f"No such service: {number}")
    line = f"load message {entry_of(group, _processes(runtime))} -- {body}"
    _one_line(runtime, line, PING_TIMEOUT, emit_done=False)
    return line


def service_line(runtime: Any, text: str, *, root: Path | None = None) -> str:
    """Turn ``service load <service id> -- <body>`` into the ``load message`` line of its entry."""
    from kernel.command.process.listen import _processes
    from kernel.services.collection import ServiceBook

    head, sep, body = text.partition(" -- ")
    words = head.split()
    if (
        not sep
        or words[:2] != ["service", "load"]
        or len(words) != 3
        or not words[2].isdigit()
        or int(words[2]) <= 0
    ):
        raise UsageError(LOAD_USAGE)
    group = ServiceBook(_folder(root) / "services.json").get(int(words[2]))
    if group is None:
        raise ValueError(f"No such service: {words[2]}")
    return f"load message {entry_of(group, _processes(runtime))} -- {body}"


def _folder(root: Path | None) -> Path:
    return Path.cwd() / ".linope" if root is None else Path(root)


def _pids(argv: list[str]) -> tuple[int, ...]:
    if not argv or argv[0] != "start" or len(argv) < 2:
        raise UsageError(USAGE)
    found: list[int] = []
    for token in argv[1:]:
        if not token.isdigit() or int(token) <= 0:
            raise UsageError(USAGE)
        found.append(int(token))
    if len(found) != len(set(found)):
        raise ValueError("The same pid was given twice")
    return tuple(found)


def _speak(
    runtime: Any = None,
    request: dict[str, Any] | None = None,
) -> int:
    from kernel.command.process.listen import PING_TIMEOUT, _one_line

    target = runtime
    if target is None:
        raise UsageError(LOAD_USAGE)
    line = service_line(target, str((request or {}).get("line") or ""))
    if _one_line(target, line, PING_TIMEOUT, emit_done=False):
        target.close_once(line)
    return 0


@guard(USAGE)
def run(
    argv: list[str],
    *,
    runtime: Any = None,
    request: dict[str, Any] | None = None,
) -> int:
    if argv[:1] == ["load"]:
        return _speak(runtime, request)
    pids = _pids(argv)
    group, lines = create_service(pids)
    return {
        "service_id": group.service_id,
        "processes": list(lines),
    }
