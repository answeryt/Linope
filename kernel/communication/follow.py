"""Take the one step a model asked for, then hand it the next page.

Each pass sends the model its page, checks the reply with ``verify``, and does
exactly that step: read memory, start a process, load a tool, or answer. The
result, or the reason it was refused, is written back to memory with a state
and a new seq. The turn ends only when the model answers.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from kernel.communication.address import (
    address_scope,
    latest_seq,
    memory_contents,
    page_messages,
)
from kernel.communication.channel import Channel, MemoryChannel
from kernel.communication.offers import command_offers
from kernel.communication.verify import Rejection, Step, verify
from kernel.hypermedia.memory_page import allowed_pointers, memory_page, page_document
from kernel.hypermedia.representation import Representation


def turn(
    service: Any,
    process: Any,
    question: str,
    *,
    channel: Channel | None = None,
    offers: Any = command_offers,
) -> Any:
    """Run one question until the model answers. Returns what the terminal shows."""
    from kernel.command.process.listen import _pid_of

    pool = getattr(process, "_pool", None)
    grants = getattr(process.activation, "grants", ()) or ()
    me = str(_pid_of(process))
    mail = channel or MemoryChannel(pool)
    mail.send(me, {"kind": "user", "content": question, "state": "asked"})
    read: list[dict[str, Any]] | None = None
    while True:
        page = memory_page(
            _rows(pool, grants),
            scope=address_scope(grants),
            seq=latest_seq(pool, grants),
            commands=offers(service, process),
            read=read,
        )
        read = None
        result = _ask_model(process, page_messages(pool, grants, page_document(page)))
        text = _text(result)
        step = verify(text, page, current_seq=latest_seq(pool, grants))
        if isinstance(step, Rejection):
            mail.send(me, {"kind": "model", "content": text, "state": "continue"})
            _refuse(mail, me, step)
            continue
        if step.way == "answer":
            mail.send(me, {"kind": "model", "content": step.body, "state": "answered"})
            return result if step.body == text.strip() else step.body
        if step.way == "read":
            read = _read(pool, grants, step.pointer)
            continue
        mail.send(me, {"kind": "model", "content": step.pointer, "state": "continue"})
        _run(service, mail, me, step, page)


def _run(service: Any, mail: Channel, me: str, step: Step, page: Representation) -> None:
    from kernel.command.convention import UsageError
    from kernel.command.process.listen import _Handed, _load, _output_text, _show
    from kernel.process.profile import ProfileUnavailable

    try:
        if step.way == "start":
            started = service.launch(list(step.argv))
            if not started:
                raise RuntimeError("这个进程没答")
            content = "\n".join(
                f"pid={process.pid} capability={step.capability}" for process in started
            )
            mail.send(me, {"kind": "other", "content": content, "state": "resulted"})
            return
        result = _load(service, "tool", step.body, step.pid, keep=False)
        _show(result)
        mail.send(me, {"kind": "tool", "content": _output_text(result), "state": "resulted"})
    except _Handed as exc:
        mail.send(me, {"kind": "tool", "content": str(exc), "state": "resulted"})
    except (UsageError, ProfileUnavailable, ValueError, KeyError, LookupError, RuntimeError, OSError) as exc:
        _refuse(
            mail,
            me,
            Rejection(
                str(exc) or type(exc).__name__,
                "pointer",
                step.pointer,
                tuple(allowed_pointers(page)),
                int(page.facts.get("seq") or 0),
            ),
        )


def _ask_model(process: Any, messages: list[dict[str, Any]]) -> Any:
    from kernel.command.process.listen import (
        _maybe_relieve,
        _note,
        _pid_of,
        _result,
        _show_notice,
    )

    _maybe_relieve(process)
    _note(process, "self")
    try:
        reply = process.ask(
            {"operation": "load", "kind": "message", "body": messages, "pid": _pid_of(process)},
            timeout=None,
            on_notice=_show_notice,
        )
    finally:
        if getattr(process, "is_alive", False):
            _note(process, "sleeping")
    return _result(reply)


def _refuse(mail: Channel, me: str, rejection: Rejection) -> None:
    detail = json.dumps(rejection.payload(), ensure_ascii=False)
    print(detail, file=sys.stderr, flush=True)
    mail.send(me, {"kind": "other", "content": detail, "state": "rejected"})


def _rows(pool: Any, grants: Any) -> list[dict[str, Any]]:
    return list((memory_contents(pool, grants) or {}).get("items") or [])


def _read(pool: Any, grants: Any, selector: str) -> list[dict[str, Any]]:
    rows = (memory_contents(pool, grants, selector) or {}).get("items") or []
    return [
        {"address": row["address"], "kind": row["kind"], "content": row["content"]}
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
