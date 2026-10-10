"""Command compatibility helpers for structured model replies."""

from __future__ import annotations

import json
import shlex
from typing import Any

from capability.model.model_runtime.blocks import turn_from_payload


def split_line(line: str) -> list[str]:
    """Split one command line while keeping backslashes literal."""
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    lexer.escape = ""
    return list(lexer)


def command_lines(text: str, names: frozenset[str] | set[str]) -> list[str]:
    """Find complete command lines in text; prose is never tokenized as a command."""
    found: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            parts = split_line(line)
        except ValueError:
            continue
        if not parts:
            continue
        if parts[0] == "linope" and len(parts) > 1 and parts[1] in names:
            found.append(" ".join(parts[1:]))
        elif parts[0] in names:
            found.append(line)
    return found


def reply_payload(reply: Any) -> Any:
    """Unwrap the process result envelope without stringifying it."""
    if isinstance(reply, dict) and reply.get("event") == "result":
        return reply.get("result")
    return reply


def reply_text(reply: Any) -> str:
    """Render only user-visible text from a process reply."""
    payload = reply_payload(reply)
    turn = turn_from_payload(payload)
    if turn is not None:
        return turn.text()
    if isinstance(payload, str):
        return payload
    return str(payload)


def command_lines_from_reply(
    reply: Any,
    names: frozenset[str] | set[str],
) -> list[str]:
    """Scan only TextBlock content; ToolCall and ToolResult never become commands."""
    payload = reply_payload(reply)
    turn = turn_from_payload(payload)
    if turn is None:
        return command_lines(reply_text(payload), names)
    found: list[str] = []
    for block in turn.blocks:
        if getattr(block, "type", None) == "text":
            found.extend(command_lines(str(getattr(block, "text", "")), names))
    return found


def tool_body(raw: str) -> Any:
    """Decode JSON or the small unquoted mapping form produced by older models."""
    value = raw.strip()
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    if not (value.startswith("{") and value.endswith("}")):
        return value
    result: dict[str, Any] = {}
    inner = value[1:-1].strip()
    if not inner:
        return result
    for item in inner.split(","):
        if ":" not in item:
            return value
        key, raw_value = item.split(":", 1)
        key = key.strip().strip("'\"")
        raw_value = raw_value.strip().strip("'\"")
        if not key:
            return value
        if raw_value == "true":
            parsed: Any = True
        elif raw_value == "false":
            parsed = False
        elif raw_value == "null":
            parsed = None
        else:
            try:
                parsed = int(raw_value)
            except ValueError:
                try:
                    parsed = float(raw_value)
                except ValueError:
                    parsed = raw_value
        result[key] = parsed
    return result
