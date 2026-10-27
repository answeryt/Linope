"""Run one model question until it answers.

The page is a projection. The pointer space decides which memory a selector may
enter. A read stays a read: it does not start a process or call a tool.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from kernel.scheduler.access import (
    address_scope,
    authorize_selector,
    latest_seq,
    memory_contents,
    page_messages,
)
from kernel.communication.channel import Channel, MemoryChannel
from kernel.communication.offers import command_offers
from kernel.communication.page import model_page
from kernel.communication.verify import Rejection, interpret
from kernel.hypermedia.memory_page import allowed_pointers, page_document
from kernel.hypermedia.representation import Representation
from kernel.scheduler.requests import ActionCall, Answer, MemoryRead


def turn(
    service: Any,
    process: Any,
    question: str,
    *,
    channel: Channel | None = None,
    offers: Any = command_offers,
    read_selector: str = "",
    note_activity: bool = True,
) -> Any:
    """Run one question until the model answers. Returns what the terminal shows.

    ``read_selector`` places those addresses on the first page. A bad address
    is refused before the question is stored. ``note_activity`` stays false when
    a handoff already recorded this process as working with its peer.
    """

    from kernel.command.process.listen import _pid_of

    pool = getattr(process, "_pool", None)
    grants = getattr(process.activation, "grants", ()) or ()
    me = str(_pid_of(process))
    mail = channel or MemoryChannel(pool)
    read: list[dict[str, Any]] | None = None
    if read_selector:
        authorize_selector(grants, read_selector)
        read = _read(pool, grants, read_selector)
    mail.send(me, {"kind": "user", "content": question, "state": "asked"})
    while True:
        page = model_page(
            _rows(pool, grants),
            scope=address_scope(grants),
            seq=latest_seq(pool, grants),
            commands=offers(service, process),
            read=read,
        )
        read = None
        result = _ask_model(
            process,
            page_messages(pool, grants, page_document(page)),
            note_activity=note_activity,
        )
        text = _text(result)
        step = interpret(text, page, current_seq=latest_seq(pool, grants))
        _note_turn(process, page, text, step)
        if isinstance(step, Rejection):
            mail.send(me, {"kind": "model", "content": text, "state": "continue"})
            _refuse(mail, me, step)
            continue
        request = step
        if isinstance(request, Answer):
            mail.send(me, {"kind": "model", "content": request.body, "state": "answered"})
            return result if request.body == text.strip() else request.body
        if isinstance(request, MemoryRead):
            read = _read_authorized(pool, grants, request, page, mail, me)
            continue
        mail.send(me, {"kind": "model", "content": step.pointer, "state": "continue"})
        _run(service, process, mail, request, page)


def _read_authorized(
    pool: Any,
    grants: Any,
    request: MemoryRead,
    page: Representation,
    mail: Channel,
    me: str,
) -> list[dict[str, Any]] | None:
    """Read only after the pointer space accepts the selector."""

    try:
        authorize_selector(grants, request.selector)
    except PermissionError as exc:
        _refuse(
            mail,
            me,
            Rejection(
                str(exc),
                "space",
                request.selector,
                tuple(allowed_pointers(page)),
                int(page.facts.get("seq") or 0),
            ),
        )
        return None
    return _read(pool, grants, request.selector)


def _run(
    service: Any,
    process: Any,
    mail: Channel,
    request: ActionCall,
    page: Representation,
) -> None:
    from kernel.command.convention import UsageError
    from kernel.command.process.listen import (
        _Handed,
        _choose,
        _hand,
        _load,
        _output_text,
        _pid_of,
        _show,
    )
    from kernel.process.profile import ProfileUnavailable

    me = str(_pid_of(process))
    try:
        if request.way == "ask":
            result = _hand(service, process, _choose(service, request.pid), request.body)
            _show(result)
            mail.send(me, {"kind": "other", "content": _text(result), "state": "resulted"})
            return
        if request.way == "start":
            launch = getattr(service, "launch", None)
            if not callable(launch):
                _refuse(
                    mail,
                    me,
                    Rejection(
                        "This window cannot start a process",
                        "pointer",
                        request.pointer,
                        tuple(allowed_pointers(page)),
                        int(page.facts.get("seq") or 0),
                    ),
                )
                return
            started = launch(list(request.argv))
            if not started:
                raise RuntimeError("This process did not answer")
            content = "\n".join(
                f"pid={process.pid} capability={request.capability}" for process in started
            )
            mail.send(me, {"kind": "other", "content": content, "state": "resulted"})
            return
        result = _load(service, "tool", request.body, request.pid, keep=False)
        _show(result)
        mail.send(me, {"kind": "tool", "content": _output_text(result), "state": "resulted"})
    except _Handed as exc:
        kind = "other" if request.way == "ask" else "tool"
        mail.send(me, {"kind": kind, "content": str(exc), "state": "resulted"})
    except (UsageError, ProfileUnavailable, ValueError, KeyError, LookupError, RuntimeError, OSError) as exc:
        _refuse(
            mail,
            me,
            Rejection(
                str(exc) or type(exc).__name__,
                "pointer",
                request.pointer,
                tuple(allowed_pointers(page)),
                int(page.facts.get("seq") or 0),
            ),
        )


def _ask_model(
    process: Any,
    messages: list[dict[str, Any]],
    *,
    note_activity: bool = True,
) -> Any:
    from kernel.command.process.listen import (
        _maybe_relieve,
        _note,
        _pid_of,
        _result,
        _show_notice,
    )

    # A handoff already relieved this process and recorded both peers.
    if note_activity:
        _maybe_relieve(process)
        _note(process, "self")
    try:
        reply = process.ask(
            {"operation": "load", "kind": "message", "body": messages, "pid": _pid_of(process)},
            timeout=None,
            on_notice=_show_notice,
        )
    finally:
        if note_activity and getattr(process, "is_alive", False):
            _note(process, "sleeping")
    return _result(reply)


def _note_turn(process: Any, page: Representation, text: str, step: Any) -> None:
    """Keep the model's own words, including a read or a refusal memory does not keep."""

    from kernel.command.process.listen import _pid_of
    from kernel.trace.journal import Journal, journal_beside, journal_path

    event: dict[str, Any] = {
        "kind": "model",
        "pid": _pid_of(process),
        "seq": int(page.facts.get("seq") or 0),
        "state": str(page.facts.get("state") or ""),
        "text": text,
    }
    if isinstance(step, Rejection):
        event["step"] = "rejected"
        event["error"] = step.error
        event["field"] = step.field
    elif isinstance(step, MemoryRead):
        event["step"] = "read"
    elif isinstance(step, Answer):
        event["step"] = "answer"
    else:
        event["step"] = step.way
    book = getattr(process, "_book", None)
    ledger = getattr(book, "_ledger", None) if book is not None else None
    path = journal_path() if ledger is None else journal_beside(ledger.path)
    Journal(path).append(event)


def _refuse(mail: Channel, me: str, rejection: Rejection) -> None:
    detail = json.dumps(rejection.payload(), ensure_ascii=False)
    print(detail, file=sys.stderr, flush=True)
    mail.send(me, {"kind": "other", "content": detail, "state": "rejected"})


def _rows(pool: Any, grants: Any) -> list[dict[str, Any]]:
    return list((memory_contents(pool, grants) or {}).get("items") or [])


def _read(pool: Any, grants: Any, selector: str) -> list[dict[str, Any]]:
    rows = (memory_contents(pool, grants, selector) or {}).get("items") or []
    return [
        {
            "address": row["address"],
            "kind": row["kind"],
            "content": row["content"],
            "time": row.get("time") or "",
        }
        for row in rows
    ]


def _text(result: Any) -> str:
    """The words of one model reply. Reasoning blocks are never read."""

    if isinstance(result, dict) and result.get("type") == "model_turn":
        return "\n".join(
            str(block.get("text") or "")
            for block in result.get("blocks") or ()
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
        )
    if isinstance(result, str):
        return result
    return "" if result is None else json.dumps(result, ensure_ascii=False)
