"""One agent turn. The loop writes kernel command lines and reads what comes back.

Asking the model, starting a peer, and running a tool are command lines. This
module does not call a provider, read the workspace, or keep a second notebook.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from capability.model.model_runtime.blocks import (
    ModelTurn,
    ReasoningBlock,
    TextBlock,
    ToolCallBlock,
    turn_from_payload,
)
from capability.prompt.prompt_load.prompt_load import system_prompt
from capability.session.session import SessionError, SessionLog, parse_page, rows_of, scope_of
from kernel.communication.page import CommandOffer

_CALL_NAME = re.compile(r"[^A-Za-z0-9_-]")


@dataclass(frozen=True)
class CommandResult:
    """Structured value the kernel returned for one command line."""

    result: Any = None
    error: str = ""


@dataclass(frozen=True)
class ToolSpec:
    """One tool the model may call. name is sent to the model; capability starts the process."""

    capability: str
    name: str
    description: str
    parameters: dict[str, Any]
    aliases: tuple[str, ...] = ()


Submit = Callable[[str], CommandResult]


def load_catalog(path: Path | None = None) -> dict[str, Any]:
    """Read the capability table the kernel already generated."""

    catalog_path = path or _capability_root() / "programs.json"
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"The capability table is unreadable: {catalog_path}")
    return payload


def declared_tools(names: list[str], catalog: dict[str, Any]) -> tuple[ToolSpec, ...]:
    """The tools named in settings. A name with no schema fails here."""

    specs: list[ToolSpec] = []
    taken: dict[str, str] = {}
    for capability in names:
        row = catalog.get(capability)
        schemas = row.get("schemas") if isinstance(row, dict) else None
        if not isinstance(schemas, list) or not schemas:
            raise ValueError(f"{capability} has no schema")
        for index, schema in enumerate(schemas):
            if not isinstance(schema, dict):
                raise ValueError(f"{capability} has no schema")
            short = str(schema.get("name") or "").strip()
            shown = capability if len(schemas) == 1 else f"{capability}.{short or index + 1}"
            name = _call_name(shown)
            owner = taken.get(name)
            if owner is not None:
                raise ValueError(f"{shown} and {owner} share the call name {name}")
            taken[name] = shown
            aliases: list[str] = []
            for alias in (short, capability, shown):
                if alias and alias != name and alias not in aliases:
                    aliases.append(alias)
            parameters = schema.get("parameters")
            specs.append(
                ToolSpec(
                    capability=capability,
                    name=name,
                    description=str(schema.get("description") or ""),
                    parameters=parameters if isinstance(parameters, dict) else {
                        "type": "object",
                        "properties": {},
                    },
                    aliases=tuple(aliases),
                )
            )
    return tuple(specs)


class Loop:
    """Ask the model, run each tool call, and ask again until the model stops."""

    def __init__(
        self,
        settings: dict[str, Any],
        submit: Submit,
        *,
        catalog: dict[str, Any] | None = None,
        identity: str | None = None,
        session_root: Path | None = None,
    ) -> None:
        model = str(settings.get("model") or "").strip()
        if not model:
            raise ValueError("agent loop has no model")
        names = settings.get("tools") or []
        if not isinstance(names, list):
            raise ValueError("agent loop tools must be a list")
        self.model = model
        self.submit = submit
        table = load_catalog() if catalog is None else catalog
        self.tools = declared_tools([str(name) for name in names], table)
        self.messages: list[dict[str, Any]] = []
        prompt = system_prompt() if identity is None else identity.strip()
        if prompt:
            self.messages.append({"role": "system", "content": prompt})
        self._pids: dict[str, int] = {}
        self._model_ready = False
        self.pid = 0
        self.thread_id = "0"
        self._seq = 1
        self._phase = "ask_model"
        self._forks: list[dict[str, Any]] = []
        self._miss: CommandResult | None = None
        self._session_root = session_root or Path.cwd()
        self._session: SessionLog | None = None
        self._replayed = False

    def bind(self, pid: int, thread_id: str = "") -> None:
        """Bind the loop to the process leader task."""

        self.pid = int(pid)
        self.thread_id = thread_id or str(self.pid)
        if self.thread_id == str(self.pid):
            self._seq = 1
        else:
            suffix = self.thread_id.rsplit(".", 1)[-1]
            self._seq = int(suffix) if suffix.isdigit() else 1

    def ask(self, question: str) -> str:
        """One user message. Later calls on this loop see the earlier messages."""

        self.prepare(question)
        while True:
            step = self.step()
            if step.get("forks") or step.get("await"):
                raise RuntimeError("The kernel runs these tools")
            line = str(step.get("line") or "")
            if step.get("pc") == "wait_tool" and not line:
                reply = self._miss or CommandResult()
            else:
                reply = self.submit(line)
            if step.get("pc") == "ask_model" and reply.error:
                raise RuntimeError(reply.error)
            done = self.land(reply)
            if done is not None:
                return done

    def prepare(self, question: str) -> None:
        """Remember the user sentence and get ready to ask the model."""

        self._resume(question)
        self.messages.append({"role": "user", "content": question})
        self._phase = "ask_model"
        self._forks = []

    def step(self) -> dict[str, Any]:
        """The next step of the current thread. This does not run the command."""

        fresh = [item for item in self._forks if not item.get("issued")]
        if self._phase == "wait_helpers" and fresh:
            return {
                "thread": self.thread_id,
                "pc": "wait_helpers",
                "registers": {"waiting": [item["id"] for item in self._forks]},
                "forks": [_step_fork(item) for item in fresh],
            }
        if self._phase == "wait_signal" or (self._phase == "wait_helpers" and self._forks):
            return {
                "thread": self.thread_id,
                "pc": "wait_signal",
                "await": True,
                "registers": {"waiting": [item["id"] for item in self._forks]},
            }
        if self._phase == "run_tool":
            call = self._pending_call
            return {
                "thread": self.thread_id,
                "pc": "wait_tool",
                "registers": {"tool": call.name, "call_id": call.id},
                "line": self._tool_line(call),
            }
        return {
            "thread": self.thread_id,
            "pc": "ask_model",
            "registers": {"question": self.messages[-1]["content"] if self.messages else ""},
            "line": self._model_line(),
        }

    def land(self, reply: CommandResult) -> str | None:
        """Store one command result. The answer comes back when the model stops."""

        if self._phase == "run_tool":
            call = self._pending_call
            self.messages.append({
                "role": "tool",
                "name": call.name,
                "tool_call_id": call.id,
                "content": reply.error or reply.result,
            })
            self._phase = "ask_model"
            self._index([(call.id, call.name)])
            return None
        if reply.error:
            raise RuntimeError(reply.error)
        turn = _parse_turn(reply.result)
        calls = _named_calls(turn)
        if not calls:
            text = turn.text()
            self.messages.append(_assistant_message(text, turn))
            if self._forks:
                self._phase = "wait_signal"
                self._index()
                return None
            self._phase = "done"
            self._index()
            return text
        self.messages.append(_assistant_message(_assistant_blocks(turn, calls), turn))
        if len(calls) == 1:
            self._pending_call = calls[0]
            self._phase = "run_tool"
            self._index()
            return None
        self._forks.extend(self._fork(call) for call in calls)
        self._phase = "wait_helpers"
        self._index()
        return None

    def note_issued(self, ids: Any) -> None:
        """These helper threads have been handed to the kernel."""

        wanted = {str(item) for item in ids}
        for fork in self._forks:
            if str(fork["id"]) in wanted:
                fork["issued"] = True

    def land_signal(self, raw: Any) -> None:
        """One completion signal. The next step asks the model with this result."""

        rows = _signal_rows(raw)
        if not rows:
            if self._forks:
                raise RuntimeError("The kernel returned a broken command result")
            self._phase = "ask_model"
            return
        item = rows[0]
        fork = self._fork_by_id(str(item.get("thread") or ""))
        call = fork["call"]
        content = str(item.get("error") or "") or _text(item.get("result"))
        if self._pair_as_tool(str(call.id)):
            self.messages.append({
                "role": "tool",
                "name": call.name,
                "tool_call_id": call.id,
                "content": content,
            })
        else:
            self.messages.append({
                "role": "user",
                "content": f"{call.name} finished:\n{content}",
            })
        self._forks = [other for other in self._forks if other is not fork]
        self._phase = "ask_model"
        self._index([(str(call.id), str(call.name))])

    def _fork_by_id(self, task_id: str) -> dict[str, Any]:
        for fork in self._forks:
            if str(fork["id"]) == task_id:
                return fork
        raise RuntimeError("The kernel returned a broken command result")

    def _pair_as_tool(self, call_id: str) -> bool:
        """A tool result can follow the assistant message that still holds this call."""

        for message in reversed(self.messages):
            if message.get("role") != "assistant":
                continue
            content = message.get("content")
            if not isinstance(content, list):
                return False
            return any(
                isinstance(block, dict)
                and block.get("type") == "tool-call"
                and str(block.get("id") or "") == call_id
                for block in content
            )
        return False

    def _fork(self, call: ToolCallBlock) -> dict[str, Any]:
        self._seq += 1
        task_id = f"{self.pid}.{self._seq}"
        line = self._tool_line(call)
        item: dict[str, Any] = {
            "id": task_id,
            "line": line,
            "registers": {"tool": call.name, "call_id": call.id},
            "call": call,
        }
        if self._miss is not None:
            item["result"] = self._miss.result
            item["error"] = self._miss.error
            item["registers"]["result"] = self._miss.result
            item["registers"]["error"] = self._miss.error
        return item

    def _model_line(self) -> str:
        if not self._model_ready:
            reply = self.submit(f"model use {self.model}")
            if reply.error:
                raise RuntimeError(reply.error)
            self._model_ready = True
        body = json.dumps(
            {"messages": self._messages_for_model(), "tools": _tool_payload(self.tools)},
            ensure_ascii=False,
        )
        return f"model run -- {body}"

    def _tool_line(self, call: ToolCallBlock) -> str:
        self._miss = None
        spec = _find(self.tools, call.name)
        if spec is None:
            self._miss = CommandResult(result=f"This page does not offer {call.name}")
            return ""
        pid = self._pids.get(spec.capability)
        if pid is None:
            reply = self.submit(CommandOffer("start", spec.capability).pointer)
            if reply.error:
                self._miss = CommandResult(result=reply.error)
                return ""
            self._remember(reply.result)
            pid = self._pids.get(spec.capability)
            if pid is None:
                self._miss = CommandResult(result=reply.result or f"Could not start {spec.capability}")
                return ""
        return CommandOffer("tool", spec.capability, pid=pid).pointer + _json_object(call.arguments)

    def _messages_for_model(self) -> list[dict[str, Any]]:
        """Drop tool calls that do not yet have a tool result."""

        answered = {
            str(message.get("tool_call_id") or "")
            for message in self.messages
            if message.get("role") == "tool" and message.get("tool_call_id")
        }
        visible: list[dict[str, Any]] = []
        for message in self.messages:
            content = message.get("content")
            if message.get("role") != "assistant" or not isinstance(content, list):
                visible.append(message)
                continue
            blocks = [
                block for block in content
                if not (
                    isinstance(block, dict)
                    and block.get("type") == "tool-call"
                    and str(block.get("id") or "") not in answered
                )
            ]
            if blocks:
                visible.append({**message, "content": blocks})
        return visible

    def _remember(self, value: Any) -> None:
        """Index process identities from a structured command value."""

        rows = value.get("processes") if isinstance(value, dict) else None
        if isinstance(value, dict) and "pid" in value:
            rows = [value]
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            pid = row.get("pid")
            name = str(row.get("capability") or "")
            if isinstance(pid, int) and pid > 0 and name:
                self._pids[name] = pid

    def _resume(self, question: str) -> None:
        """Read the session once, then keep only the lines this process did not just say."""

        if self.pid <= 0 or self._replayed:
            if self._replayed:
                self._index()
            return
        page = self._page()
        self._replayed = True
        if page is None:
            return
        self._open_session(page)
        if self._session is None:
            return
        earlier = self._session.entries()
        if earlier:
            self.messages.extend(self._restore(page, earlier))
        fresh = self._session.note(rows_of(page))
        skip = _question_real(fresh, rows_of(page), question)
        extra = [item for item in fresh if item.real != skip]
        if extra:
            self.messages.extend(self._session.messages(self._read, extra))

    def _restore(self, page: dict[str, Any], earlier: list[Any]) -> list[dict[str, Any]]:
        """Read the saved addresses. A list for some other memory is set aside."""

        visible = {str(row.get("real") or "") for row in rows_of(page)}
        if any(item.real not in visible for item in earlier):
            try:
                return self._session.messages(self._read, earlier)
            except SessionError:
                if self._session is not None:
                    self._session.restart()
                return []
        return self._session.messages(self._read, earlier)

    def _index(self, calls: list[tuple[str, str]] | None = None) -> None:
        """Ask show for this process and append addresses that are new."""

        if self.pid <= 0:
            return
        page = self._page()
        if page is None:
            return
        self._open_session(page)
        if self._session is None:
            return
        self._session.note(rows_of(page), calls or [])

    def _open_session(self, page: dict[str, Any]) -> None:
        if self._session is not None:
            return
        scope = scope_of(page)
        if not scope:
            return
        self._session = SessionLog(self._session_root, scope)

    def _page(self, real: str = "") -> dict[str, Any] | None:
        selector = self._stored(real)
        line = f"show {self.pid}" if not selector else f"show {self.pid} {selector}"
        reply = self.submit(line)
        if real and (reply.error or parse_page(reply.result) is None):
            raise SessionError(f"This session line is gone: {real}")
        if reply.error:
            return None
        page = parse_page(reply.result)
        if real and (page is None or not _has_real(page, real)):
            raise SessionError(f"This session line is gone: {real}")
        return page

    def _stored(self, real: str) -> str:
        """A stored name, read through this session's scope.

        ``message/1`` on the session list is the memory's own name. ``show``
        with that bare name uses this process's page table instead. The scope
        pointer, ``chat/message/1``, follows the stored row.
        """

        scope = "" if self._session is None else self._session.scope
        if not real or not scope or real.startswith(f"{scope}/"):
            return real
        return f"{scope}/{real}"

    def _read(self, real: str) -> dict[str, Any] | None:
        page = self._page(real)
        if page is None:
            return None
        for row in rows_of(page):
            if str(row.get("real") or "") == real:
                return row
        return None


def _capability_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _step_fork(fork: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": fork.get("id") or "",
        "line": fork.get("line") or "",
        "registers": fork.get("registers") or {},
    }


def _signal_rows(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        if not raw.strip():
            return []
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("The kernel returned a broken command result") from exc
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise RuntimeError("The kernel returned a broken command result")
    return [item for item in raw if isinstance(item, dict)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _call_name(shown: str) -> str:
    """A function name the chat API accepts. A dot in a capability becomes an underscore."""

    name = _CALL_NAME.sub("_", shown)
    if not name:
        raise ValueError(f"{shown} has no call name")
    return name


def _tool_payload(tools: tuple[ToolSpec, ...]) -> list[dict[str, Any]]:
    return [
        {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
        for tool in tools
    ]


def _find(tools: tuple[ToolSpec, ...], name: str) -> ToolSpec | None:
    for tool in tools:
        if name == tool.name or name == tool.capability or name in tool.aliases:
            return tool
    return None


def _named_calls(turn: ModelTurn) -> tuple[ToolCallBlock, ...]:
    named = [block for block in turn.tool_calls() if block.name]
    calls: list[ToolCallBlock] = []
    for index, block in enumerate(named, start=1):
        if block.id:
            calls.append(block)
            continue
        calls.append(ToolCallBlock(
            name=block.name,
            arguments=block.arguments,
            id=f"call-{index}",
            index=block.index,
        ))
    return tuple(calls)


def _assistant_message(content: Any, turn: ModelTurn) -> dict[str, Any]:
    """One assistant row. Thinking stays beside the words the model already said."""

    message: dict[str, Any] = {"role": "assistant", "content": content}
    reasoning = "".join(
        block.text for block in turn.blocks if isinstance(block, ReasoningBlock) and block.text
    )
    if reasoning:
        message["reasoning_content"] = reasoning
    return message


def _assistant_blocks(turn: ModelTurn, calls: tuple[ToolCallBlock, ...]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = [
        {"type": "text", "text": block.text}
        for block in turn.blocks
        if isinstance(block, TextBlock) and block.text
    ]
    for call in calls:
        blocks.append({
            "type": "tool-call",
            "id": call.id,
            "name": call.name,
            "arguments": call.arguments,
        })
    return blocks


def _parse_turn(raw: Any) -> ModelTurn:
    if isinstance(raw, dict):
        turn = turn_from_payload(raw)
        if turn is not None:
            return turn
    text = raw.strip() if isinstance(raw, str) else str(raw or "")
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            turn = turn_from_payload(payload)
            if turn is not None:
                return turn
    return ModelTurn(blocks=(TextBlock(text=raw),))


def _has_real(page: dict[str, Any], real: str) -> bool:
    return any(str(row.get("real") or "") == real for row in rows_of(page))


def _question_real(fresh: list[Any], rows: list[dict[str, Any]], question: str) -> str:
    """The newest user row that is this sentence. It is already about to be said."""

    bodies = {str(row.get("real") or ""): str(row.get("content") or "") for row in rows}
    kinds = {str(row.get("real") or ""): str(row.get("kind") or "") for row in rows}
    match = [
        item
        for item in fresh
        if kinds.get(item.real) == "user" and bodies.get(item.real) == question
    ]
    if not match:
        return ""
    return max(match, key=lambda item: item.seq).real


def _json_object(value: Any) -> str:
    if isinstance(value, str):
        try:
            parsed = json.loads(value) if value else {}
        except json.JSONDecodeError:
            parsed = {"value": value}
    elif isinstance(value, dict):
        parsed = value
    elif value is None:
        parsed = {}
    else:
        parsed = {"value": value}
    if not isinstance(parsed, dict):
        parsed = {"value": parsed}
    return json.dumps(parsed, ensure_ascii=False)
