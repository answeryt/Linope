"""Hand one line to the process that is already waiting.

``load`` and ``ping`` are sent to that capability's own program. ``ask`` hands
one task to another living process. ``list``, ``show``, and ``trace`` are
answered in this window. None of these lines are written into the resource ledger.
"""

from __future__ import annotations

import json
import shlex
import sys
import time
from pathlib import Path
from typing import Any

from kernel.command.convention import UsageError
from kernel.communication.address import (
    keep_memory_system,
    memory_contents,
    memory_grant,
    remember,
)
_PROMPT_SUFFIXES = {".txt", ".md", ".json"}

PING_TIMEOUT = 1.0
_SEQ = 0


def hold(service: Any, *, ping: bool = False, once: bool = False, lines: Any = None, timeout: float = PING_TIMEOUT) -> bool:
    """Stay open. With ``once``, close after one load has been handed to a process."""
    try:
        _open_programs(service)
        for line in _member_lines(service):
            print(line, flush=True)
        if ping and not _startup_ping(service, timeout):
            print("This process did not answer", file=sys.stderr)
            return False
        for raw in sys.stdin if lines is None else lines:
            if _one_line(service, raw, timeout) and once:
                return True
        return True
    except KeyboardInterrupt:
        return True
    finally:
        service.close()


def ask_ping(service: Any, pid: str | int | None = None, timeout: float = PING_TIMEOUT) -> dict[str, Any] | None:
    """Ask one living process. A wrong sequence, id, or a silence is no answer."""
    process = _choose(service, pid)
    seq = _next_seq()
    question = {
        "operation": "ping",
        "pid": _pid_of(process),
        "seq": seq,
        "channel": process.channel_name(),
    }
    reply = process.ask(question, timeout=timeout)
    if not isinstance(reply, dict):
        return None
    if reply.get("event") != "pong":
        return None
    if reply.get("seq") != seq or int(reply.get("pid") or 0) != question["pid"]:
        return None
    return reply


def _startup_ping(service: Any, timeout: float) -> bool:
    processes = [process for process in _processes(service) if process.is_alive]
    if not processes:
        time.sleep(timeout)
        return False
    for process in processes:
        reply = ask_ping(service, _pid_of(process), timeout)
        if reply is None:
            return False
        print(reply, flush=True)
    return True


def _one_line(service: Any, raw: str, timeout: float, *, emit_done: bool = True) -> bool:
    """Handle one line. True only after a load was handed to the process."""
    text = raw.strip()
    if not text:
        return False
    handed = False
    try:
        parsed = _parse_line(text)
        if parsed[0] == "list":
            _print_list(service)
        elif parsed[0] == "show":
            _print_show(service, parsed[1], parsed[2] if len(parsed) > 2 else "")
        elif parsed[0] == "trace":
            _print_trace(service, parsed[1])
        elif parsed[0] == "ping":
            reply = ask_ping(service, parsed[1], timeout)
            if reply is None:
                print("This process did not answer", file=sys.stderr)
            else:
                print(reply, flush=True)
        elif parsed[0] == "ask":
            try:
                result = _ask(service, parsed[1], parsed[2])
            except _Handed as handed_error:
                print(handed_error, file=sys.stderr)
            else:
                _show(result)
            handed = True
        else:
            try:
                selector = parsed[4] if len(parsed) > 4 else ""
                result = _load(service, parsed[1], parsed[2], parsed[3], selector=selector)
            except _Handed as handed_error:
                print(handed_error, file=sys.stderr)
            else:
                _show(result)
            handed = True
    except (UsageError, ValueError, LookupError, RuntimeError, TypeError, PermissionError) as exc:
        print(exc, file=sys.stderr)
    if emit_done:
        print(json.dumps({"type": "done"}, ensure_ascii=False), flush=True)
    return handed


def _load(
    service: Any,
    kind: str,
    body: Any,
    pid: str | int | None,
    *,
    selector: str = "",
    keep: bool = True,
) -> Any:
    process = _choose(service, pid)
    addressed = bool(selector)
    if addressed and (
        kind != "message" or not isinstance(body, str) or not _pages(service, process)
    ):
        raise UsageError("usage: load message <full pid> <address> -- <question>")
    if not addressed and _remember_prompt(process, body):
        return None
    if kind == "message" and isinstance(body, str) and _pages(service, process):
        from kernel.scheduler.model_turn import turn

        return turn(service, process, body, read_selector=selector)
    _maybe_relieve(process)
    message = {
        "operation": "load",
        "kind": kind,
        "body": body,
        "pid": _pid_of(process),
    }
    _note(process, "self")
    try:
        reply = process.ask(message, timeout=None, on_notice=_show_notice)
    finally:
        if getattr(process, "is_alive", False):
            _note(process, "sleeping")
    result = _result(reply)
    if keep:
        _keep_output(process, kind, body, result)
    return result


def _pages(service: Any, process: Any) -> bool:
    """A process with memory talks through a page. Launching is a separate ability."""
    del service
    grants = getattr(getattr(process, "activation", None), "grants", ()) or ()
    return memory_grant(grants) is not None


def _ask(service: Any, pid: str | int, task: str) -> Any:
    """Hand one task to the named process. The sender's memory stays here."""
    receiver = _choose(service, pid)
    sender = _sender(service, receiver)
    result = _hand(service, sender, receiver, task)
    _remember(sender, "other", _output_text(result))
    return result


def _hand(service: Any, sender: Any, receiver: Any, task: str) -> Any:
    """Run one task on ``receiver``. Memory there makes it a page turn."""
    sender_id = str(_pid_of(sender))
    receiver_id = str(_pid_of(receiver))
    _maybe_relieve(receiver)
    _note(sender, "with", receiver_id, "task")
    _note(receiver, "with", sender_id, "task")
    try:
        return _task_on(service, receiver, task)
    finally:
        if getattr(sender, "is_alive", False):
            _note(sender, "sleeping")
        if getattr(receiver, "is_alive", False):
            _note(receiver, "sleeping")


def _task_on(service: Any, receiver: Any, task: str) -> Any:
    """A receiver with memory runs one turn. Any other receiver gets the task text."""
    grants = getattr(getattr(receiver, "activation", None), "grants", ()) or ()
    if memory_grant(grants) is not None:
        from kernel.scheduler.model_turn import turn

        return turn(service, receiver, task, note_activity=False)
    reply = receiver.ask(
        {
            "operation": "load",
            "kind": "message",
            "body": task,
            "pid": _pid_of(receiver),
        },
        timeout=None,
        on_notice=_show_notice,
    )
    return _result(reply)


def _remember_prompt(process: Any, body: Any) -> bool:
    """A prompt file is copied into memory and is not sent to the model."""
    loaded = _prompt_load(body)
    if loaded is None:
        return False
    path, place = loaded
    grants = getattr(process.activation, "grants", ()) or ()
    if memory_grant(grants) is None:
        raise RuntimeError("This process has no memory")
    keep_memory_system(
        process._pool,
        grants,
        path.read_text(encoding="utf-8"),
        name=str(path),
        place=place,
    )
    return True


def _keep_output(process: Any, kind: str, body: Any, result: Any) -> None:
    if kind == "message" and isinstance(body, str):
        _remember(process, "model", _output_text(result))
    elif kind == "tool":
        _remember(process, "tool", _output_text(result))


def _remember(process: Any, kind: str, content: str) -> None:
    grants = getattr(process.activation, "grants", ()) or ()
    remember(getattr(process, "_pool", None), grants, kind, content)


def _output_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


def _result(reply: Any) -> Any:
    if not isinstance(reply, dict):
        raise RuntimeError("This process is gone")
    if reply.get("event") == "error":
        raise _Handed(str(reply.get("error") or "This process did not answer"))
    return reply.get("result")


def _note(process: Any, activity: str, counterpart: str = "", way: str = "") -> None:
    log = _activity(process)
    if log is None:
        return
    log.append(_pid_of(process), activity, counterpart, way)


def _maybe_relieve(process: Any) -> None:
    """Add one helper before this handoff when pressure says so."""
    book = getattr(process, "_book", None)
    if book is None:
        return
    record = book.get(_pid_of(process))
    if record is None:
        return
    from kernel.calculate.measure import measure
    from kernel.load_balancing.relieve import relieve

    log = _activity(process)
    activity = "sleeping"
    if log is not None:
        latest = log.latest(_pid_of(process))
        if latest is not None:
            activity = str(latest.get("activity") or "sleeping")
    settings = getattr(getattr(process, "activation", None), "settings", None) or {}
    model = str(settings.get("id") or "") if isinstance(settings, dict) else ""
    pressure = measure(
        pool=getattr(process, "_pool", None),
        record=record,
        book=book,
        activity=activity,
        model=model,
    )
    relieve(book, record.pid, pressure, delegating=True)


def _sender(service: Any, receiver: Any) -> Any:
    """The one other living process. A task needs exactly one sender."""
    receiver_id = _pid_of(receiver)
    others = [
        process
        for process in _processes(service)
        if getattr(process, "is_alive", False)
        and _pid_of(process) != receiver_id
    ]
    if len(others) == 1:
        return others[0]
    raise UsageError("Handing off a task requires exactly one other living process besides the peer")


def _prompt_load(body: Any) -> tuple[Path, int | None] | None:
    """A prompt file, optionally placed by a leading positive integer."""
    if not isinstance(body, str):
        return None
    raw = body.strip()
    if not raw or "\n" in raw or "\r" in raw:
        return None
    place: int | None = None
    path_text = raw
    head, sep, tail = raw.partition(" ")
    if sep and head.isdigit() and int(head) > 0 and tail.strip():
        place = int(head)
        path_text = tail.strip()
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if path.suffix.lower() not in _PROMPT_SUFFIXES or not path.is_file():
        return None
    return path, place


class _Handed(Exception):
    """The load reached the process, and the process reported an error."""


def _show_notice(notice: dict[str, Any]) -> None:
    """A text fragment is the same event the terminal already prints."""
    text = notice.get("text")
    if not text:
        return
    from kernel.command.screen.live_stream import publish_text

    publish_text(str(text))


def _show(result: Any) -> None:
    if isinstance(result, str):
        print(result, flush=True)
        return
    if isinstance(result, dict) and result.get("type") == "model_turn":
        return
    if result is not None:
        print(result, flush=True)


def parse_line(line: str) -> tuple[Any, ...]:
    """Split one window line into its command, process id, and body."""
    if " -- " in line:
        head, body = line.split(" -- ", 1)
        argv = shlex.split(head, posix=True)
        content: str | None = body
    else:
        argv = shlex.split(line, posix=True)
        content = None
    if argv and argv[0] == "list":
        if len(argv) == 1 and content is None:
            return ("list",)
        raise UsageError("usage: list")
    if argv and argv[0] == "show":
        if len(argv) >= 2 and content is None:
            return ("show", argv[1], " ".join(argv[2:]))
        raise UsageError("usage: show <full pid> [address]")
    if argv and argv[0] == "trace":
        if len(argv) == 2 and content is None:
            return ("trace", argv[1])
        raise UsageError("usage: trace <full pid>")
    if argv and argv[0] == "ping":
        if len(argv) == 2 and argv[1] and content is None:
            return ("ping", argv[1])
        raise UsageError("usage: ping <full pid>")
    if argv and argv[0] == "ask":
        if len(argv) == 2 and argv[1] and content is not None:
            return ("ask", argv[1], content)
        raise UsageError("usage: ask <peer pid> -- <task>")
    if not argv or argv[0] != "load" or content is None or len(argv) < 3:
        raise UsageError("usage: load <kind> <full pid> -- <body>")
    selector = " ".join(argv[3:])
    if selector and argv[1] != "message":
        raise UsageError("usage: load <kind> <full pid> -- <body>")
    return ("load", argv[1], _body(content), argv[2], selector)


_parse_line = parse_line


def _body(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return text
    return text


def _choose(service: Any, token: str | int | None) -> Any:
    wanted = _parse_pid(token)
    alive = [process for process in _processes(service) if getattr(process, "is_alive", False)]
    matches = [
        process
        for process in alive
        if wanted is not None and _pid_of(process) == wanted
    ]
    if len(matches) == 1:
        return matches[0]
    living = ", ".join(str(_pid_of(process)) for process in alive) or "none"
    raise UsageError(f"Write the full pid. Still alive: {living}")


def _pid_of(process: Any) -> int:
    activation = getattr(process, "activation", None)
    value = getattr(activation, "pid", None)
    if value:
        return int(value)
    return int(getattr(process, "pid", 0) or 0)


def _parse_pid(token: str | int | None) -> int | None:
    if token is None or isinstance(token, bool):
        return None
    if isinstance(token, int):
        return token if token > 0 else None
    text = str(token).strip()
    if not text.isdigit():
        return None
    value = int(text)
    return value if value > 0 else None


def _open_programs(service: Any) -> None:
    for process in _processes(service):
        if not getattr(process, "is_alive", False):
            continue
        opener = getattr(process, "open_program", None)
        if opener is None:
            continue
        opener()
        log = _activity(process)
        if log is not None:
            log.append(_pid_of(process), "sleeping")


def _print_list(service: Any) -> None:
    for process in _processes(service):
        record = _record(process)
        status = "" if record is None else record.status.value
        activity = _shown_activity(process, record)
        print(
            f"pid={_pid_of(process)} activity={activity} status={status}",
            flush=True,
        )


def _print_show(service: Any, pid: str, selector: str = "") -> None:
    import json

    from kernel.hypermedia.process_page import page_document, process_page

    process = _by_id(service, pid)
    record = _record(process)
    if record is None:
        raise UsageError(f"No such process: {pid}")
    activity = _shown_activity(process, record)
    counterpart, way = _with_fields(_latest(process), activity)
    page = process_page(
        record,
        activity,
        counterpart,
        way,
        _live_shares(service, process),
    )
    document = page_document(page)
    contents = memory_contents(
        getattr(process, "_pool", None),
        getattr(process.activation, "grants", ()) or (),
        selector,
    )
    if contents is not None:
        document["memory"] = contents
    print(json.dumps(document, ensure_ascii=False), flush=True)


def _print_trace(service: Any, pid: str) -> None:
    import json

    process = _by_id(service, pid)
    log = _activity(process)
    rows = () if log is None else log.for_process(_pid_of(process))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False), flush=True)


def _shown_activity(process: Any, record: Any) -> str:
    if record is not None and str(getattr(record.status, "value", record.status)) == "closed":
        return "closed"
    if not getattr(process, "is_alive", False):
        return "closed"
    latest = _latest(process)
    if latest is None:
        return "sleeping"
    return str(latest.get("activity") or "sleeping")


def _latest(process: Any) -> dict[str, Any] | None:
    log = _activity(process)
    if log is None:
        return None
    return log.latest(_pid_of(process))


def _record(process: Any) -> Any:
    book = getattr(process, "_book", None)
    if book is None:
        return None
    return book.get(_pid_of(process))


def _by_id(service: Any, token: str | int) -> Any:
    wanted = _parse_pid(token)
    matches = [
        process
        for process in _processes(service)
        if wanted is not None and _pid_of(process) == wanted
    ]
    if len(matches) == 1:
        return matches[0]
    living = ", ".join(str(_pid_of(process)) for process in _processes(service)) or "none"
    raise UsageError(f"Write the full pid. Still alive: {living}")


def _with_fields(latest: dict[str, Any] | None, activity: str) -> tuple[str, str]:
    if activity != "with" or latest is None:
        return "", ""
    return str(latest.get("with") or ""), str(latest.get("way") or "")


def _shared_memory_id(record: Any) -> str:
    if record is None:
        return ""
    for lease in getattr(record, "leases", ()) or ():
        if str(getattr(lease, "kind", "")) != "memory":
            continue
        if str(getattr(lease, "share_mode", "")) != "shared":
            continue
        return str(lease.resource_id)
    return ""


def _live_shares(service: Any, process: Any) -> tuple[str, ...]:
    record = _record(process)
    memory_id = _shared_memory_id(record)
    if not memory_id:
        return ()
    pid = _pid_of(process)
    found: list[str] = []
    for other in _processes(service):
        if not getattr(other, "is_alive", False):
            continue
        other_id = _pid_of(other)
        if other_id == pid:
            continue
        if _shared_memory_id(_record(other)) == memory_id:
            found.append(str(other_id))
    return tuple(found)


def _saved_shares(book: Any, record: Any) -> tuple[str, ...]:
    memory_id = _shared_memory_id(record)
    if not memory_id:
        return ()
    found: list[str] = []
    for other in book.records():
        if other.pid == record.pid:
            continue
        if str(getattr(other.status, "value", other.status)) == "closed":
            continue
        if _shared_memory_id(other) == memory_id:
            found.append(str(other.pid))
    return tuple(found)


def _activity(process: Any) -> Any:
    book = getattr(process, "_book", None)
    ledger = getattr(book, "_ledger", None) if book is not None else None
    if ledger is None:
        return None
    from pathlib import Path

    from kernel.trace.activity import ActivityLog

    return ActivityLog(Path(ledger.path).with_name("activity.jsonl"))


def _processes(service: Any) -> list[Any]:
    reader = getattr(service, "processes", None)
    if callable(reader):
        return list(reader())
    found: list[Any] = []
    for group in getattr(service, "_processes", {}).values():
        found.extend(group)
    return found


def _capability_of(process: Any) -> str:
    activation = getattr(process, "activation", None)
    definition = getattr(activation, "definition", None)
    if definition is not None:
        return str(getattr(definition, "instance_id", "") or "")
    return str(getattr(process, "capability", "") or "")


def _member_lines(service: Any) -> list[str]:
    return [
        f"pid={_pid_of(process)} capability={_capability_of(process)}"
        for process in _processes(service)
    ]


def _next_seq() -> int:
    global _SEQ
    _SEQ += 1
    return _SEQ


def saved_list() -> int:
    """Print the accounts left in the ledger file."""
    book = _saved_book()
    log = _saved_log()
    for record in book.records():
        latest = None if log is None else log.latest(record.pid)
        activity = _saved_activity(record, latest)
        print(
            f"pid={record.pid} "
            f"activity={activity} status={record.status.value}",
            flush=True,
        )
    return 0


def saved_show(token: str) -> int:
    """Print the current page for one saved account."""
    from kernel.hypermedia.process_page import page_document, process_page

    book = _saved_book()
    pid = _parse_pid(token)
    record = None if pid is None else book.get(pid)
    if record is None:
        raise UsageError(f"No such process: {token}")
    latest = _saved_log().latest(record.pid)
    activity = _saved_activity(record, latest)
    counterpart, way = _with_fields(latest, activity)
    page = process_page(record, activity, counterpart, way, _saved_shares(book, record))
    print(json.dumps(page_document(page), ensure_ascii=False), flush=True)
    return 0


def saved_trace(token: str) -> int:
    """Print the activity trail for one saved account."""
    book = _saved_book()
    pid = _parse_pid(token)
    if pid is None or book.get(pid) is None:
        raise UsageError(f"No such process: {token}")
    for row in _saved_log().for_process(pid):
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return 0


def _saved_book() -> Any:
    from pathlib import Path

    from kernel.process.ledger import ProcessLedger
    from kernel.process.resource_record import ProcessResourceBook

    path = Path.cwd() / ".linope" / "processes.json"
    return ProcessResourceBook(ProcessLedger(path))


def _saved_log() -> Any:
    from pathlib import Path

    from kernel.trace.activity import ActivityLog

    return ActivityLog(Path.cwd() / ".linope" / "activity.jsonl")


def _saved_activity(record: Any, latest: dict[str, Any] | None) -> str:
    if str(getattr(record.status, "value", record.status)) == "closed":
        return "closed"
    if latest is None:
        return "sleeping"
    return str(latest.get("activity") or "sleeping")
