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
from kernel.resource.address import (
    keep_memory_system,
    memory_contents,
    memory_grant,
    memory_messages,
    remember,
)
from kernel.services.contracts import ServiceRequest

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
            print("这个进程没答", file=sys.stderr)
            return False
        for raw in sys.stdin if lines is None else lines:
            if _one_line(service, raw, timeout) and once:
                return True
        return True
    except KeyboardInterrupt:
        return True
    finally:
        service.close()


def ask_ping(service: Any, process_id: str | None = None, timeout: float = PING_TIMEOUT) -> dict[str, Any] | None:
    """Ask one living process. A wrong sequence, id, or a silence is no answer."""
    process = _choose(service, process_id)
    seq = _next_seq()
    question = {
        "operation": "ping",
        "process_id": process.activation.process_id,
        "seq": seq,
        "channel": process.channel_name(),
    }
    reply = process.ask(question, timeout=timeout)
    if not isinstance(reply, dict):
        return None
    if reply.get("event") != "pong":
        return None
    if reply.get("seq") != seq or reply.get("process_id") != question["process_id"]:
        return None
    return reply


def _startup_ping(service: Any, timeout: float) -> bool:
    processes = [process for process in _processes(service) if process.is_alive]
    if not processes:
        time.sleep(timeout)
        return False
    for process in processes:
        reply = ask_ping(service, process.activation.process_id, timeout)
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
            _print_show(service, parsed[1])
        elif parsed[0] == "trace":
            _print_trace(service, parsed[1])
        elif parsed[0] == "ping":
            reply = ask_ping(service, parsed[1], timeout)
            if reply is None:
                print("这个进程没答", file=sys.stderr)
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
                result = _load(service, parsed[1], parsed[2], parsed[3])
            except _Handed as handed_error:
                print(handed_error, file=sys.stderr)
            else:
                _show(result)
            handed = True
    except (UsageError, ValueError, LookupError, RuntimeError, TypeError) as exc:
        print(exc, file=sys.stderr)
    if emit_done:
        print(json.dumps({"type": "done"}, ensure_ascii=False), flush=True)
    return handed


def _load(service: Any, kind: str, body: Any, process_id: str | None) -> Any:
    process = _choose(service, process_id)
    if _remember_prompt(process, body):
        return None
    sent = _question_with_memory(process, body)
    message = ServiceRequest(kind=kind, body=sent, operation="load").message()
    message["process_id"] = process.activation.process_id
    _note(process, "self")
    try:
        reply = process.ask(message, timeout=None, on_notice=_show_notice)
    finally:
        if getattr(process, "is_alive", False):
            _note(process, "sleeping")
    result = _result(reply)
    _keep_output(process, kind, body, result)
    return result


def _ask(service: Any, process_id: str, task: str) -> Any:
    """Hand one task to the named process. The sender's memory stays here."""
    receiver = _choose(service, process_id)
    sender = _sender(service, receiver)
    sender_id = sender.activation.process_id
    receiver_id = receiver.activation.process_id
    _note(sender, "with", receiver_id, "task")
    _note(receiver, "with", sender_id, "task")
    try:
        message = ServiceRequest(
            kind="message",
            body=_task_body(receiver, task),
            operation="load",
        ).message()
        message["process_id"] = receiver_id
        reply = receiver.ask(message, timeout=None, on_notice=_show_notice)
    finally:
        if getattr(sender, "is_alive", False):
            _note(sender, "sleeping")
        if getattr(receiver, "is_alive", False):
            _note(receiver, "sleeping")
    result = _result(reply)
    _remember(sender, "other", _output_text(result))
    return result


def _remember_prompt(process: Any, body: Any) -> bool:
    """A prompt file is copied into memory and is not sent to the model."""
    path = _prompt_file(body)
    if path is None:
        return False
    grants = getattr(process.activation, "grants", ()) or ()
    if memory_grant(grants) is None:
        raise RuntimeError("这个进程没有记忆")
    keep_memory_system(process._pool, grants, path.read_text(encoding="utf-8"))
    return True


def _question_with_memory(process: Any, body: Any) -> Any:
    """Keep this question, then send everything already in memory."""
    if not isinstance(body, str):
        return body
    grants = getattr(process.activation, "grants", ()) or ()
    if memory_grant(grants) is None:
        return body
    _remember(process, "user", body)
    return memory_messages(getattr(process, "_pool", None), grants)


def _task_body(process: Any, task: str) -> Any:
    """The receiver's own memory, then this task. The sender's memory is absent."""
    grants = getattr(process.activation, "grants", ()) or ()
    if memory_grant(grants) is None:
        return task
    messages = memory_messages(getattr(process, "_pool", None), grants)
    messages.append({"role": "user", "content": task})
    return messages


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
        raise RuntimeError("这个进程没了")
    if reply.get("event") == "error":
        raise _Handed(str(reply.get("error") or "这个进程没答"))
    return reply.get("result")


def _note(process: Any, activity: str, counterpart: str = "", way: str = "") -> None:
    log = _activity(process)
    if log is None:
        return
    log.append(process.activation.process_id, activity, counterpart, way)


def _sender(service: Any, receiver: Any) -> Any:
    """The one other living process. A task needs exactly one sender."""
    receiver_id = receiver.activation.process_id
    others = [
        process
        for process in _processes(service)
        if getattr(process, "is_alive", False)
        and process.activation.process_id != receiver_id
    ]
    if len(others) == 1:
        return others[0]
    raise UsageError("交任务时，除了对方，还要正好有一个还活着的进程")


def _prompt_file(body: Any) -> Path | None:
    if not isinstance(body, str):
        return None
    raw = body.strip()
    if not raw or "\n" in raw or "\r" in raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if path.suffix.lower() not in _PROMPT_SUFFIXES or not path.is_file():
        return None
    return path


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


def _parse_line(line: str) -> tuple[Any, ...]:
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
        raise UsageError("用法: list")
    if argv and argv[0] == "show":
        if len(argv) == 2 and content is None:
            return ("show", argv[1])
        raise UsageError("用法: show <完整进程号>")
    if argv and argv[0] == "trace":
        if len(argv) == 2 and content is None:
            return ("trace", argv[1])
        raise UsageError("用法: trace <完整进程号>")
    if argv and argv[0] == "ping":
        if len(argv) == 2 and argv[1] and content is None:
            return ("ping", argv[1])
        raise UsageError("用法: ping <完整进程号>")
    if argv and argv[0] == "ask":
        if len(argv) == 2 and argv[1] and content is not None:
            return ("ask", argv[1], content)
        raise UsageError("用法: ask <对方进程号> -- <要做的事>")
    if not argv or argv[0] != "load" or content is None or len(argv) != 3:
        raise UsageError("用法: load <种类> <完整进程号> -- <内容>")
    return ("load", argv[1], _body(content), argv[2])


def _body(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return text
    return text


def _choose(service: Any, process_id: str | None) -> Any:
    alive = [process for process in _processes(service) if getattr(process, "is_alive", False)]
    matches = [
        process
        for process in alive
        if process_id and process.activation.process_id == process_id
    ]
    if len(matches) == 1:
        return matches[0]
    living = "、".join(process.activation.process_id for process in alive) or "没有"
    raise UsageError(f"请写上完整进程号。还活着: {living}")


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
            log.append(process.activation.process_id, "sleeping")


def _print_list(service: Any) -> None:
    for process in _processes(service):
        record = _record(process)
        status = "" if record is None else record.status.value
        activity = _shown_activity(process, record)
        print(
            f"process_id={process.activation.process_id} pid={process.pid} "
            f"activity={activity} status={status}",
            flush=True,
        )


def _print_show(service: Any, process_id: str) -> None:
    import json

    from kernel.hypermedia.process_page import page_document, process_page

    process = _by_id(service, process_id)
    record = _record(process)
    if record is None:
        raise UsageError(f"没有这个进程: {process_id}")
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
    )
    if contents is not None:
        document["memory"] = contents
    print(json.dumps(document, ensure_ascii=False), flush=True)


def _print_trace(service: Any, process_id: str) -> None:
    import json

    _by_id(service, process_id)
    log = _activity(_by_id(service, process_id))
    rows = () if log is None else log.for_process(process_id)
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
    return log.latest(process.activation.process_id)


def _record(process: Any) -> Any:
    book = getattr(process, "_book", None)
    if book is None:
        return None
    return book.get(process.activation.process_id)


def _by_id(service: Any, process_id: str) -> Any:
    matches = [
        process
        for process in _processes(service)
        if process.activation.process_id == process_id
    ]
    if len(matches) == 1:
        return matches[0]
    living = "、".join(process.activation.process_id for process in _processes(service)) or "没有"
    raise UsageError(f"请写上完整进程号。还活着: {living}")


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
    process_id = process.activation.process_id
    found: list[str] = []
    for other in _processes(service):
        if not getattr(other, "is_alive", False):
            continue
        other_id = other.activation.process_id
        if other_id == process_id:
            continue
        if _shared_memory_id(_record(other)) == memory_id:
            found.append(other_id)
    return tuple(found)


def _saved_shares(book: Any, record: Any) -> tuple[str, ...]:
    memory_id = _shared_memory_id(record)
    if not memory_id:
        return ()
    found: list[str] = []
    for other in book.records():
        if other.process_id == record.process_id:
            continue
        if str(getattr(other.status, "value", other.status)) == "closed":
            continue
        if _shared_memory_id(other) == memory_id:
            found.append(other.process_id)
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


def _member_lines(service: Any) -> list[str]:
    return [
        f"process_id={member.process_id} pid={member.pid} capability={member.capability}"
        for member in service.members()
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
        latest = None if log is None else log.latest(record.process_id)
        activity = _saved_activity(record, latest)
        print(
            f"process_id={record.process_id} pid={record.pid} "
            f"activity={activity} status={record.status.value}",
            flush=True,
        )
    return 0


def saved_show(process_id: str) -> int:
    """Print the current page for one saved account."""
    from kernel.hypermedia.process_page import page_document, process_page

    book = _saved_book()
    record = book.get(process_id)
    if record is None:
        raise UsageError(f"没有这个进程: {process_id}")
    latest = _saved_log().latest(process_id)
    activity = _saved_activity(record, latest)
    counterpart, way = _with_fields(latest, activity)
    page = process_page(record, activity, counterpart, way, _saved_shares(book, record))
    print(json.dumps(page_document(page), ensure_ascii=False), flush=True)
    return 0


def saved_trace(process_id: str) -> int:
    """Print the activity trail for one saved account."""
    book = _saved_book()
    if book.get(process_id) is None:
        raise UsageError(f"没有这个进程: {process_id}")
    for row in _saved_log().for_process(process_id):
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
