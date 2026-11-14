"""One capability process. A user message becomes kernel command lines.

The kernel starts this process, binds its resource record, and runs each
command the loop writes. This file only keeps the stdin door open.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from capability.agent_loop.linope.loop import CommandResult, Loop


def main() -> None:
    """Answer ``load message`` until the pipe closes."""

    _use_utf8(sys.stdin)
    _use_utf8(sys.stdout)
    first = sys.stdin.readline()
    if not first:
        return
    try:
        startup = json.loads(first)
    except json.JSONDecodeError as exc:
        _write({"event": "error", "error": str(exc)})
        return
    activation = startup.get("activation")
    if not isinstance(activation, dict):
        _write({"event": "error", "error": "The startup message does not name this capability"})
        return
    pid = int(activation.get("pid") or 0)
    try:
        session = Loop(_settings(activation), _submit)
        session.bind(pid, str(activation.get("thread_id") or ""))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _write({"event": "error", "error": str(exc)})
        return
    _write({"event": "ready", "pid": pid})
    while True:
        raw = sys.stdin.readline()
        if not raw:
            return
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            _write({"event": "error", "error": str(exc)})
            continue
        if not isinstance(message, dict):
            _write({"event": "error", "error": "The request must be one record"})
            continue
        try:
            _handle(session, pid, message)
        except Exception as exc:
            _write({"event": "error", "error": str(exc)})


def _settings(activation: dict[str, Any]) -> dict[str, Any]:
    context = activation.get("resource_context")
    if not isinstance(context, dict):
        return {}
    settings = context.get("settings")
    return settings if isinstance(settings, dict) else {}


def _handle(session: Loop, pid: int, message: dict[str, Any]) -> None:
    if message.get("operation") == "ping":
        _write({
            "event": "pong",
            "pid": pid,
            "seq": message.get("seq"),
            "channel": message.get("channel") or "",
        })
        return
    if message.get("operation") != "load" or message.get("kind") != "message":
        _write({"event": "error", "error": "This process only accepts load message"})
        return
    body = message.get("body")
    question = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    session.prepare(question)
    while True:
        step = session.step()
        forks = step.get("forks")
        if forks:
            session.note_issued(item.get("id") for item in forks)
            _write({
                "event": "fork",
                "thread": step.get("thread") or "",
                "pc": step.get("pc") or "wait_helpers",
                "registers": step.get("registers") or {},
                "threads": [_public_fork(item) for item in forks],
            })
            _land_signal(session, _read_result())
            continue
        if step.get("await"):
            _write({
                "event": "await",
                "thread": step.get("thread") or "",
                "pc": step.get("pc") or "wait_signal",
                "registers": step.get("registers") or {},
            })
            _land_signal(session, _read_result())
            continue
        _write({
            "event": "command",
            "thread": step.get("thread") or "",
            "pc": step.get("pc") or "",
            "registers": step.get("registers") or {},
            "line": step.get("line") or "",
        })
        done = session.land(_read_result())
        if done is not None:
            _write({"event": "result", "result": done})
            return


def _land_signal(session: Loop, reply: CommandResult) -> None:
    if reply.error:
        raise RuntimeError(reply.error)
    session.land_signal(reply.result)


def _public_fork(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id") or "",
        "pc": item.get("pc") or "wait_tool",
        "line": item.get("line") or "",
        "registers": item.get("registers") or {},
    }


def _read_result() -> CommandResult:
    raw = sys.stdin.readline()
    if not raw:
        raise RuntimeError("The kernel returned a broken command result")
    try:
        reply = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The kernel returned a broken command result") from exc
    if not isinstance(reply, dict) or reply.get("event") != "command_result":
        raise RuntimeError("The kernel returned a broken command result")
    return CommandResult(
        result=reply.get("result"),
        error=str(reply.get("error") or ""),
    )


def _submit(line: str) -> CommandResult:
    _write({"event": "command", "line": line})
    return _read_result()


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _use_utf8(stream: Any) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    reconfigure(encoding="utf-8")


if __name__ == "__main__":
    main()
