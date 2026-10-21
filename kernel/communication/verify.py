"""Check one model output against the page it was given. Nothing runs here.

Three forms are accepted: a ``continue`` JSON, one bare command line, or a plain
answer. A bare command line is a ``continue`` whose pointer is that line, so it
passes the same checks and is never refused for being a command line.
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


@dataclass(frozen=True)
class Step:
    """One step that passed. ``way`` is read, start, tool, or answer."""

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
        return refuse(f"这一页已经过期：页是 {seq}，记忆已经到了 {int(current_seq)}", "seq", text)
    if not text:
        return refuse("回答是空的", "format", text)
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return refuse(f"JSON 解析不了：{exc.msg}（第 {exc.lineno} 行第 {exc.colno} 列）", "format", text)
        if not isinstance(data, dict):
            return refuse("JSON 必须是一个对象", "format", text)
        if data.get("state") != "continue":
            return refuse("state 只能是 continue", "state", json.dumps(data.get("state"), ensure_ascii=False))
        pointer = data.get("pointer")
        if not isinstance(pointer, str) or not pointer.strip():
            return refuse("pointer 必须是页里的一个指针", "pointer", json.dumps(pointer, ensure_ascii=False))
        handle = data.get("handle")
        if handle is not None and not _handle_matches(page, pointer, handle):
            return refuse("handle 对不上这一页，页可能已经变了", "seq", str(handle))
        return _pointer(pointer.strip(), data.get("body"), page, refuse)
    if _is_command_line(text):
        return _pointer(text, None, page, refuse)
    return Step(ANSWER, ANSWER, text)


def _pointer(pointer: str, body: Any, page: Representation, refuse: Any) -> Step | Rejection:
    if pointer == ANSWER:
        if not isinstance(body, str) or not body.strip():
            return refuse("answer 的 body 必须是给用户的回答", "body", json.dumps(body, ensure_ascii=False))
        return Step(ANSWER, ANSWER, body.strip())
    words = _strip_linope(pointer)
    head = words.split(None, 1)[0] if words else ""
    if head.split("/", 1)[0] in MEMORY_CLASSES:
        return _read(words, page, refuse)
    if head == "process":
        return _start(words, page, refuse)
    if head == "load":
        return _tool(words, body, page, refuse)
    if head in COMMAND_WORDS:
        return refuse("这条命令不在当前页里", "pointer", words)
    return refuse("这个指针不在当前页里", "pointer", words)


def _read(selector: str, page: Representation, refuse: Any) -> Step | Rejection:
    known = {link.resource_id for link in page.links}
    wanted: list[str] = []
    for part in selector.replace(",", " ").split():
        match = re.fullmatch(r"(system)(?:/0)?|(message|task|artifact)/(\d+)(?:-(\d+))?", part)
        if match is None:
            return refuse("地址写错了，写成 message/0 或 message/0-2", "pointer", part)
        if match.group(1):
            addresses = ["system/0"]
        else:
            start = int(match.group(3))
            end = int(match.group(4) or start)
            if end < start:
                return refuse("地址范围要从小写到大", "pointer", part)
            addresses = [f"{match.group(2)}/{index}" for index in range(start, end + 1)]
        missing = [address for address in addresses if address not in known]
        if missing:
            return refuse(f"这个地址不在当前页里：{missing[0]}", "pointer", part)
        wanted.extend(addresses)
    return Step("read", " ".join(wanted))


def _start(line: str, page: Representation, refuse: Any) -> Step | Rejection:
    from kernel.command.parser import UsageError
    from kernel.command.process.start import START_USAGE, parse_start_options

    try:
        argv = shlex.split(line, posix=True)
    except ValueError as exc:
        return refuse(f"命令拆不开：{exc}", "pointer", line)
    if len(argv) < 2 or argv[1] != "start":
        return refuse("这条命令不在当前页里", "pointer", line)
    try:
        parsed = parse_start_options(argv[2:])
    except (UsageError, ValueError) as exc:
        return refuse(str(exc) or START_USAGE, "pointer", line)
    capability = str(parsed[0])
    if f"start:{capability}" not in _relations(page):
        return refuse(f"当前页里没有启动 {capability} 这一条", "pointer", line)
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
        return refuse("这条命令不在当前页里，模型只能用 load tool", "pointer", line)
    token = str(parsed[3])
    if not token.isdigit():
        return refuse("请写上页里给的完整进程号", "pointer", line)
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
        return refuse(f"进程号 {pid} 对不上当前页里的工具", "pointer", line)
    arguments = parsed[2]
    if not isinstance(arguments, dict):
        return refuse("load tool 的正文必须是 JSON 对象", "body", str(arguments))
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


def _check_arguments(arguments: dict[str, Any], schema: dict[str, Any]) -> tuple[str, str] | None:
    properties = schema.get("properties") or {}
    for name in schema.get("required") or ():
        if name not in arguments:
            return f"body.{name}", f"缺少 {name}"
    for name, value in arguments.items():
        rule = properties.get(name)
        if not isinstance(rule, dict):
            if schema.get("additionalProperties") is False:
                return f"body.{name}", f"不认识的参数 {name}"
            continue
        kind = rule.get("type")
        if kind == "string":
            if not isinstance(value, str) or (name in (schema.get("required") or ()) and not value.strip()):
                return f"body.{name}", f"{name} 必须是非空字符串"
        elif kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                return f"body.{name}", f"{name} 必须是整数"
        elif kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return f"body.{name}", f"{name} 必须是数字"
        elif kind == "boolean" and not isinstance(value, bool):
            return f"body.{name}", f"{name} 必须是 true 或 false"
        elif kind == "array" and not isinstance(value, list):
            return f"body.{name}", f"{name} 必须是数组"
        elif kind == "object" and not isinstance(value, dict):
            return f"body.{name}", f"{name} 必须是对象"
        low, high = rule.get("minimum"), rule.get("maximum")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if (low is not None and value < low) or (high is not None and value > high):
                return f"body.{name}", f"{name} 要在 {low} 到 {high} 之间"
        choices = rule.get("enum")
        if isinstance(choices, list) and value not in choices:
            return f"body.{name}", f"{name} 只能是 {'、'.join(map(str, choices))}"
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
