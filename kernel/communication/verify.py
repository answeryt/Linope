"""Check one model output against the page it was given. Nothing runs here.

Three forms are accepted: a ``continue`` JSON, one bare command line, or a plain
answer. A bare command line is a ``continue`` whose pointer is that line, so it
passes the same checks and is never refused for being a command line. Prose
around exactly one command is that command. Several commands are refused.
"""

from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from typing import Any

from kernel.hypermedia.memory_page import ANSWER, allowed_pointers
from kernel.hypermedia.representation import Representation

COMMAND_WORDS = frozenset({"process", "load", "ask", "show", "list", "trace", "ping"})
MEMORY_CLASSES = frozenset({"system", "message", "task", "artifact"})
_GOT_LIMIT = 500
_FENCE = re.compile(r"^```[A-Za-z]*\s*\n(?P<inner>.*?)\n?```$", re.DOTALL)
_TICKS = re.compile(r"^`(?P<inner>[^`\n]+)`$")
_ADDRESS = re.compile(r"(system)(?:/0)?|(message|task|artifact)/\d+(?:-\d+)?")
_COMMAND_HEADS = frozenset({"process", "load", "ask"})


@dataclass(frozen=True)
class Step:
    """One step that passed. ``way`` is read, start, tool, ask, or answer."""

    way: str
    pointer: str
    body: Any = None
    argv: tuple[str, ...] = ()
    pid: int = 0
    capability: str = ""


@dataclass(frozen=True)
class Rejection:
    """Why the output was not run. The model reads this on its next page."""

    error: str
    field: str
    got: str
    allowed: tuple[str, ...] = field(default_factory=tuple)
    seq: int = 0

    def payload(self) -> dict[str, Any]:
        return {
            "error": self.error,
            "field": self.field,
            "got": self.got,
            "allowed": list(self.allowed),
            "seq": self.seq,
        }


def verify(output: Any, page: Representation, *, current_seq: int | None = None) -> Step | Rejection:
    """Return the one step this output asks for, or the reason it cannot run."""
    seq = int(page.facts.get("seq") or 0)
    allowed = tuple(allowed_pointers(page))
    text = _unfence(str(output or "").strip())

    def refuse(error: str, where: str, got: str) -> Rejection:
        return Rejection(error, where, _clip(got), allowed, seq)

    if current_seq is not None and int(current_seq) != seq:
        return refuse(f"This page has expired: the page is {seq}, but memory is already at {int(current_seq)}", "seq", text)
    if not text:
        return refuse("Answer is empty", "format", text)
    if text.startswith("{"):
        try:
            data = _one_json_object(text)
        except json.JSONDecodeError as exc:
            picked = _pick_command(text, page, refuse)
            if picked is not None:
                return picked
            return refuse(f"JSON could not be parsed: {exc.msg} (line {exc.lineno}, column {exc.colno})", "format", text)
        if not isinstance(data, dict):
            return refuse("JSON must be an object", "format", text)
        if data.get("state") != "continue":
            return refuse("state must be continue", "state", json.dumps(data.get("state"), ensure_ascii=False))
        pointer = data.get("pointer")
        if not isinstance(pointer, str) or not pointer.strip():
            return refuse("pointer must be a pointer on the page", "pointer", json.dumps(pointer, ensure_ascii=False))
        handle = data.get("handle")
        if handle is not None and not _handle_matches(page, pointer, handle):
            return refuse("handle does not match this page; the page may have changed", "seq", str(handle))
        return _pointer(pointer.strip(), data.get("body"), page, refuse)
    if _is_command_line(text):
        return _pointer(text, None, page, refuse)
    picked = _pick_command(text, page, refuse)
    if picked is not None:
        return picked
    return Step(ANSWER, ANSWER, text)


def _one_json_object(text: str) -> Any:
    """One JSON object. A second copy of that same object is the first one again."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        if exc.msg != "Extra data":
            raise
        data, end = json.JSONDecoder().raw_decode(text)
        if text[end:].strip() != text[:end].strip():
            raise
        return data


def interpret(output: Any, page: Representation, *, current_seq: int | None = None) -> Any:
    """Turn one model output into a typed request. Running it belongs to the scheduler."""

    step = verify(output, page, current_seq=current_seq)
    if isinstance(step, Rejection):
        return step
    from kernel.scheduler.requests import classify

    return classify(step)


def _pointer(pointer: str, body: Any, page: Representation, refuse: Any) -> Step | Rejection:
    if pointer == ANSWER:
        if not isinstance(body, str) or not body.strip():
            return refuse("answer body must be the reply to the user", "body", json.dumps(body, ensure_ascii=False))
        return Step(ANSWER, ANSWER, body.strip())
    words = _strip_linope(pointer)
    head = words.split(None, 1)[0] if words else ""
    if head.split("/", 1)[0] in MEMORY_CLASSES:
        return _read(words, page, refuse)
    if head == "process":
        return _start(words, page, refuse)
    if head == "load":
        return _tool(words, body, page, refuse)
    if head == "ask":
        return _ask(words, body, page, refuse)
    if head in COMMAND_WORDS:
        return refuse("This command is not on the current page", "pointer", words)
    if any(link.relation == "memory" and link.resource_id.strip() == words for link in page.links):
        return refuse("This is a memory resource; read an address inside it, for example message/0", "pointer", words)
    return refuse("This pointer is not on the current page", "pointer", words)


def _read(selector: str, page: Representation, refuse: Any) -> Step | Rejection:
    known = {link.resource_id for link in page.links}
    wanted: list[str] = []
    for part in selector.replace(",", " ").split():
        match = re.fullmatch(r"(system)(?:/0)?|(message|task|artifact)/(\d+)(?:-(\d+))?", part)
        if match is None:
            return refuse("Bad address; write message/0 or message/0-2", "pointer", part)
        if match.group(1):
            addresses = ["system/0"]
        else:
            start = int(match.group(3))
            end = int(match.group(4) or start)
            if end < start:
                return refuse("Address range must go from low to high", "pointer", part)
            addresses = [f"{match.group(2)}/{index}" for index in range(start, end + 1)]
        missing = [address for address in addresses if address not in known]
        if missing:
            return refuse(f"This address is not on the current page: {missing[0]}", "pointer", part)
        wanted.extend(addresses)
    return Step("read", " ".join(wanted))


def _start(line: str, page: Representation, refuse: Any) -> Step | Rejection:
    from kernel.command.parser import UsageError
    from kernel.command.process.start import START_USAGE, parse_start_options

    try:
        argv = shlex.split(line, posix=True)
    except ValueError as exc:
        return refuse(f"Command could not be split: {exc}", "pointer", line)
    if len(argv) < 2 or argv[1] != "start":
        return refuse("This command is not on the current page", "pointer", line)
    try:
        parsed = parse_start_options(argv[2:])
    except (UsageError, ValueError) as exc:
        return refuse(str(exc) or START_USAGE, "pointer", line)
    capability = str(parsed[0])
    if f"start:{capability}" not in _relations(page):
        return refuse(f"The current page has no start entry for {capability}", "pointer", line)
    return Step(
        "start",
        "process start " + shlex.join(argv[2:]),
        argv=tuple(argv[2:]),
        capability=capability,
    )


def _tool(line: str, body: Any, page: Representation, refuse: Any) -> Step | Rejection:
    from kernel.command.parser import UsageError
    from kernel.command.process.listen import parse_line

    line = _with_body(line, body)
    try:
        parsed = parse_line(line)
    except (UsageError, ValueError) as exc:
        return refuse(str(exc), "pointer", line)
    if parsed[0] != "load" or parsed[1] != "tool":
        return refuse("This command is not on the current page; the model can only use load tool", "pointer", line)
    token = str(parsed[3])
    if not token.isdigit():
        return refuse("Write the full pid given on the page", "pointer", line)
    pid = int(token)
    offer = next(
        (
            (relation, detail)
            for relation, detail in _relations(page).items()
            if relation.startswith("tool:") and int(detail.get("pid") or 0) == pid
        ),
        None,
    )
    if offer is None:
        return refuse(f"pid {pid} does not match a tool on the current page", "pointer", line)
    arguments = parsed[2]
    if not isinstance(arguments, dict):
        return refuse("load tool body must be a JSON object", "body", str(arguments))
    problem = _check_arguments(arguments, offer[1].get("schema") or {})
    if problem is not None:
        where, error = problem
        return refuse(error, where, json.dumps(arguments, ensure_ascii=False))
    return Step(
        "tool",
        f"load tool {pid} -- {json.dumps(arguments, ensure_ascii=False)}",
        body=arguments,
        pid=pid,
        capability=str(offer[1].get("capability") or ""),
    )


def _ask(line: str, body: Any, page: Representation, refuse: Any) -> Step | Rejection:
    line = _with_body(line, body).rstrip()
    if line.endswith(" --"):
        line += " "
    head, _, task = line.partition(" -- ")
    words = head.split()
    if len(words) != 2:
        return refuse("usage: ask <pid> -- <task>", "pointer", line)
    token = words[1]
    if not token.isdigit():
        return refuse("Write the full pid given on the page", "pointer", line)
    pid = int(token)
    offer = next(
        (
            detail
            for relation, detail in _relations(page).items()
            if relation.startswith("ask:") and int(detail.get("pid") or 0) == pid
        ),
        None,
    )
    if offer is None:
        return refuse(f"pid {pid} does not match a model on the current page", "pointer", line)
    task = task.strip()
    if not task:
        return refuse("ask body must be the task", "body", line)
    return Step(
        "ask",
        f"ask {pid} -- {task}",
        body=task,
        pid=pid,
        capability=str(offer.get("capability") or ""),
    )


def _check_arguments(arguments: dict[str, Any], schema: dict[str, Any]) -> tuple[str, str] | None:
    properties = schema.get("properties") or {}
    for name in schema.get("required") or ():
        if name not in arguments:
            return f"body.{name}", f"missing {name}"
    for name, value in arguments.items():
        rule = properties.get(name)
        if not isinstance(rule, dict):
            if schema.get("additionalProperties") is False:
                return f"body.{name}", f"Unknown parameter {name}"
            continue
        kind = rule.get("type")
        if kind == "string":
            if not isinstance(value, str) or (name in (schema.get("required") or ()) and not value.strip()):
                return f"body.{name}", f"{name} must be a non-empty string"
        elif kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                return f"body.{name}", f"{name} must be an integer"
        elif kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return f"body.{name}", f"{name} must be a number"
        elif kind == "boolean" and not isinstance(value, bool):
            return f"body.{name}", f"{name} must be true or false"
        elif kind == "array" and not isinstance(value, list):
            return f"body.{name}", f"{name} must be an array"
        elif kind == "object" and not isinstance(value, dict):
            return f"body.{name}", f"{name} must be an object"
        low, high = rule.get("minimum"), rule.get("maximum")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if (low is not None and value < low) or (high is not None and value > high):
                return f"body.{name}", f"{name} must be between {low} and {high}"
        choices = rule.get("enum")
        if isinstance(choices, list) and value not in choices:
            return f"body.{name}", f"{name} must be one of {', '.join(map(str, choices))}"
    return None


def _with_body(line: str, body: Any) -> str:
    """Put a JSON body after the pointer's ``--`` when the pointer left it empty."""
    if body is None:
        return line
    stripped = line.rstrip()
    if stripped.endswith(" --"):
        stripped = stripped[:-3]
    elif " -- " in line:
        head, rest = line.split(" -- ", 1)
        if rest.strip():
            return line
        stripped = head
    text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    return f"{stripped.rstrip()} -- {text}"


def _relations(page: Representation) -> dict[str, dict[str, Any]]:
    details = page.facts.get("details") or {}
    return {
        link.relation: dict(details.get(link.relation) or {})
        for link in page.links
    }


def _handle_matches(page: Representation, pointer: str, handle: Any) -> bool:
    wanted = _strip_linope(pointer)
    return any(
        link.handle == str(handle)
        for link in page.links
        if wanted.startswith(link.resource_id.strip()) or link.relation == wanted
    )


def _pick_command(text: str, page: Representation, refuse: Any) -> Step | Rejection | None:
    """The one command buried in prose. ``None`` means the text has no command."""
    lines = _command_lines(text)
    if not lines:
        return None
    if len(lines) > 1:
        return refuse("Only one command is allowed", "pointer", text)
    line = lines[0]
    if line.startswith("{"):
        data = json.loads(line)
        return _pointer(str(data.get("pointer") or "").strip(), data.get("body"), page, refuse)
    return _pointer(line, None, page, refuse)


def _command_lines(text: str) -> list[str]:
    found: list[str] = []
    for raw in text.splitlines():
        line = _plain_line(raw)
        if _looks_like_command(line):
            found.append(line)
    return found


def _plain_line(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith("```"):
        return ""
    if line.startswith("`") and line.endswith("`") and line.count("`") == 2:
        line = line[1:-1].strip()
    return _strip_linope(line)


def _looks_like_command(line: str) -> bool:
    if not line:
        return False
    if line.startswith("{") and line.endswith("}"):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return False
        return (
            isinstance(data, dict)
            and data.get("state") == "continue"
            and isinstance(data.get("pointer"), str)
            and bool(data["pointer"].strip())
        )
    head = line.split(None, 1)[0]
    if head in _COMMAND_HEADS:
        return True
    return _ADDRESS.fullmatch(head) is not None


def _is_command_line(text: str) -> bool:
    if "\n" in text:
        return False
    words = _strip_linope(text).split(None, 1)
    return bool(words) and words[0] in COMMAND_WORDS


def _strip_linope(text: str) -> str:
    stripped = text.strip()
    if stripped == "linope" or stripped.startswith("linope "):
        return stripped[len("linope"):].strip()
    return stripped


def _unfence(text: str) -> str:
    match = _FENCE.match(text)
    if match:
        text = match.group("inner").strip()
    match = _TICKS.match(text)
    return match.group("inner").strip() if match else text


def _clip(text: str) -> str:
    return text if len(text) <= _GOT_LIMIT else text[:_GOT_LIMIT] + "…"
