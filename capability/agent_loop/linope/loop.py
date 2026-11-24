"""One agent turn. The loop writes kernel command lines and reads what comes back.

Asking the model, starting a peer, and running a tool are command lines. This
module does not call a provider, read the workspace, or keep a second notebook.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
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
    remote_name: str = ""


Submit = Callable[[str], CommandResult]


@dataclass
class _Shared:
    """What every turn of one process uses together."""

    lock: threading.RLock = field(default_factory=threading.RLock)
    pids: dict[str, int] = field(default_factory=dict)
    model_ready: bool = False
    tools: tuple[ToolSpec, ...] = ()
    model: str = ""
    pid: int = 0
    prompt: str = ""


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
    ) -> None:
        model = str(settings.get("model") or "").strip()
        if not model:
            raise ValueError("agent loop has no model")
        names = settings.get("tools") or []
        if not isinstance(names, list):
            raise ValueError("agent loop tools must be a list")
        chosen = [str(name) for name in names]
        table = load_catalog() if catalog is None else catalog
        shared = _Shared()
        shared.model = model
        shared.tools = declared_tools(chosen, table)
        shared.prompt = system_prompt() if identity is None else identity.strip()
        self._shared = shared
        self._submit_fn = submit
        self.messages: list[dict[str, Any]] = []
        self.thread_id = "0"
        self._phase = "ask_model"
        self._pending_issue: list[ToolCallBlock] = []
        self._miss: CommandResult | None = None
        self._origin = 0
        self._replaced_prompt = False

    @property
    def model(self) -> str:
        return self._shared.model

    @property
    def tools(self) -> tuple[ToolSpec, ...]:
        return self._shared.tools

    @tools.setter
    def tools(self, value: tuple[ToolSpec, ...]) -> None:
        self._shared.tools = value

    @property
    def submit(self) -> Submit:
        return self._submit_fn

    @submit.setter
    def submit(self, value: Submit) -> None:
        self._submit_fn = value

    @property
    def pid(self) -> int:
        return self._shared.pid

    @pid.setter
    def pid(self, value: int) -> None:
        self._shared.pid = int(value)

    @property
    def _pids(self) -> dict[str, int]:
        return self._shared.pids

    @property
    def _model_ready(self) -> bool:
        return self._shared.model_ready

    @_model_ready.setter
    def _model_ready(self, value: bool) -> None:
        self._shared.model_ready = bool(value)

    def open_turn(self, thread_id: str) -> Loop:
        """One more sentence. It reads the same memory when it starts."""

        turn = Loop.__new__(Loop)
        turn._shared = self._shared
        turn._submit_fn = self._submit_fn
        turn.messages = []
        turn.thread_id = str(thread_id)
        turn._phase = "ask_model"
        turn._pending_issue = []
        turn._miss = None
        turn._origin = 0
        turn._replaced_prompt = False
        return turn

    def bind(self, pid: int, thread_id: str = "") -> None:
        """Bind the loop to the process leader task."""

        self.pid = int(pid)
        self.thread_id = thread_id or str(self.pid)

    def prepare(self, question: str) -> None:
        """Read the finished memory, then remember this sentence."""

        prior = self._history()
        self.messages = []
        if self._shared.prompt and not self._replaced_prompt:
            self.messages.append({"role": "system", "content": self._shared.prompt})
        self.messages.extend(prior)
        self._origin = len(self.messages)
        self.messages.append({"role": "user", "content": question})
        self._phase = "ask_model"
        self._pending_issue = []

    def step(self) -> dict[str, Any]:
        """The next step of the current thread. This does not run the command."""

        if self._phase == "wait_helpers" and self._pending_issue:
            forks = [self._issue(call) for call in self._pending_issue]
            self._pending_issue = []
            return {
                "thread": self.thread_id,
                "pc": "wait_helpers",
                "registers": {"waiting": [str(item["registers"].get("call_id") or "") for item in forks]},
                "forks": [_step_fork(item) for item in forks],
            }
        if self._phase in {"wait_signal", "wait_helpers"}:
            return {
                "thread": self.thread_id,
                "pc": "wait_signal",
                "await": True,
                "registers": {"waiting": [call_id for call_id, _name in self._unanswered()]},
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
            return None
        if reply.error:
            raise RuntimeError(reply.error)
        queued = _queued_signals(reply.result)
        if queued is not None:
            for item in queued:
                self.land_signal([item])
            return None
        turn = _parse_turn(reply.result)
        calls = _named_calls(turn)
        if not calls:
            text = turn.text()
            self.messages.append(_assistant_message(text, turn))
            if self._unanswered():
                self._phase = "wait_signal"
                return None
            self._phase = "done"
            return text
        self.messages.append(_assistant_message(_assistant_blocks(turn, calls), turn))
        if len(calls) == 1:
            self._pending_call = calls[0]
            self._phase = "run_tool"
            return None
        self._pending_issue = list(calls)
        self._phase = "wait_helpers"
        return None

    def land_signal(self, raw: Any) -> None:
        """One completion signal. The next step asks the model with this result."""

        rows = _signal_rows(raw)
        if not rows:
            if self._unanswered():
                raise RuntimeError("The kernel returned a broken command result")
            self._phase = "ask_model"
            return
        self._land_row(rows[0])

    def _land_row(self, item: dict[str, Any]) -> None:
        """Write one finished tool call back into this turn."""

        call_id = str(item.get("call_id") or "")
        name = self._call_name(call_id)
        if not name:
            raise RuntimeError("The kernel returned a broken command result")
        content = str(item.get("error") or "") or _text(item.get("result"))
        if self._pair_as_tool(call_id):
            self.messages.append({
                "role": "tool",
                "name": name,
                "tool_call_id": call_id,
                "content": content,
            })
        else:
            self.messages.append({
                "role": "user",
                "content": f"{name} finished:\n{content}",
                "tool_call_id": call_id,
                "name": name,
                "output": content,
            })
        self._phase = "ask_model"

    def _call_name(self, call_id: str) -> str:
        """The tool name this turn already recorded for this call."""

        if not call_id:
            return ""
        for message in self.messages:
            content = message.get("content")
            if message.get("role") != "assistant" or not isinstance(content, list):
                continue
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool-call"
                    and str(block.get("id") or "") == call_id
                ):
                    return str(block.get("name") or "")
        return ""

    def _unanswered(self) -> list[tuple[str, str]]:
        """Tool calls in this turn that do not yet have a tool result."""

        answered = {
            str(message.get("tool_call_id") or "")
            for message in self.messages
            if message.get("tool_call_id")
        }
        found: list[tuple[str, str]] = []
        for message in self.messages:
            content = message.get("content")
            if message.get("role") != "assistant" or not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool-call":
                    continue
                call_id = str(block.get("id") or "")
                if call_id and call_id not in answered:
                    found.append((call_id, str(block.get("name") or "")))
        return found

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

    def _history(self) -> list[dict[str, Any]]:
        """Finished memory rows. Trailing user lines are turns that have not ended."""

        if self.pid <= 0:
            self._replaced_prompt = False
            return []
        reply = self.submit(f"show {self.pid}")
        if reply.error:
            self._replaced_prompt = False
            return []
        page = parse_page(reply.result)
        if page is None:
            self._replaced_prompt = False
            return []
        rows = rows_of(page)
        last = -1
        for index, row in enumerate(rows):
            if str(row.get("kind") or "") in {"model", "tool"}:
                last = index
        if last < 0:
            kept = [row for row in rows if str(row.get("kind") or "") == "system"]
        else:
            kept = rows[: last + 1]
        self._replaced_prompt = any(
            str(row.get("kind") or "") == "system" and str(row.get("state") or "") == "!"
            for row in kept
        )
        return _messages_from_memory(kept)

    def memory_rows(self) -> list[dict[str, str]]:
        """Lines this turn produced, apart from the question and the final answer."""

        found: list[dict[str, str]] = []
        for message in self.messages[self._origin + 1 : -1]:
            row = _memory_row(message)
            if row is not None:
                found.append(row)
        return found

    def _issue(self, call: ToolCallBlock) -> dict[str, Any]:
        """One helper the kernel will number and run. The call id travels in the registers."""

        line = self._tool_line(call)
        item: dict[str, Any] = {
            "id": "",
            "line": line,
            "registers": {"tool": call.name, "call_id": call.id},
        }
        if self._miss is not None:
            item["result"] = self._miss.result
            item["error"] = self._miss.error
            item["registers"]["result"] = self._miss.result
            item["registers"]["error"] = self._miss.error
        return item

    def _model_line(self) -> str:
        with self._shared.lock:
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
        with self._shared.lock:
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
        arguments = _arguments(call.arguments)
        body: Any = {"name": spec.remote_name, "arguments": arguments} if spec.remote_name else arguments
        return CommandOffer("tool", spec.capability, pid=pid).pointer + _json_object(body)

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
            if message.get("role") == "user" and message.get("tool_call_id"):
                visible.append({"role": "user", "content": content})
                continue
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


def adopt_remote_tools(
    existing: tuple[ToolSpec, ...],
    capability: str,
    rows: list[Any],
) -> tuple[ToolSpec, ...]:
    """Tools one capability is already serving. A shared call name fails."""

    specs: list[ToolSpec] = []
    seen: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{capability} returned no tool name")
        remote = str(row.get("name") or "").strip()
        if not remote:
            raise ValueError(f"{capability} returned no tool name")
        name = _call_name(remote)
        previous = seen.get(name)
        if previous is not None:
            raise ValueError(f"{remote} and {previous} share the call name {name}")
        seen[name] = remote
        parameters = row.get("parameters")
        specs.append(ToolSpec(
            capability=capability,
            name=name,
            description=str(row.get("description") or ""),
            parameters=parameters if isinstance(parameters, dict) else {
                "type": "object",
                "properties": {},
            },
            aliases=(remote,) if remote != name else (),
            remote_name=remote,
        ))
    taken = {tool.name: tool.capability for tool in existing}
    merged = list(existing)
    for spec in specs:
        owner = taken.get(spec.name)
        if owner is not None:
            raise ValueError(f"{spec.remote_name or spec.name} and {owner} share the call name {spec.name}")
        taken[spec.name] = spec.capability
        merged.append(spec)
    return tuple(merged)


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


def parse_page(value: Any) -> dict[str, Any] | None:
    """Validate a structured process page returned by the kernel."""

    if isinstance(value, dict):
        payload = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
    else:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def rows_of(page: dict[str, Any]) -> list[dict[str, Any]]:
    """Memory rows on this page. A page with no memory has none."""

    memory = page.get("memory")
    if not isinstance(memory, dict):
        return []
    items = memory.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _memory_row(message: dict[str, Any]) -> dict[str, str] | None:
    """One memory line for a message this turn produced."""

    role = str(message.get("role") or "")
    if role == "tool" or (role == "user" and message.get("tool_call_id")):
        payload = {
            "type": "tool-result",
            "request_id": str(message.get("tool_call_id") or ""),
            "name": str(message.get("name") or ""),
            "output": message.get("output", message.get("content")),
        }
        return {"kind": "tool", "content": json.dumps(payload, ensure_ascii=False)}
    if role != "assistant":
        return None
    content = message.get("content")
    reasoning = str(message.get("reasoning_content") or "")
    if isinstance(content, list) or reasoning:
        blocks: list[dict[str, Any]] = []
        if reasoning:
            blocks.append({"type": "reasoning", "text": reasoning})
        if isinstance(content, list):
            blocks.extend(block for block in content if isinstance(block, dict))
        elif content:
            blocks.append({"type": "text", "text": str(content)})
        payload = {"type": "model_turn", "blocks": blocks, "finish_reason": "stop"}
        return {"kind": "model", "content": json.dumps(payload, ensure_ascii=False)}
    return {"kind": "model", "content": str(content or "")}


def _messages_from_memory(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rebuild model messages from memory rows."""

    messages: list[dict[str, Any]] = []
    for row in rows:
        kind = str(row.get("kind") or "")
        content = str(row.get("content") or "")
        if kind == "system":
            messages.append({"role": "system", "content": content})
            continue
        if kind == "user":
            messages.append({"role": "user", "content": content})
            continue
        if kind == "model":
            messages.append(_model_from_memory(content))
            continue
        if kind != "tool":
            continue
        restored = _tool_from_memory(content)
        if restored is None:
            messages.append({"role": "user", "content": content})
            continue
        call_id = str(restored.get("tool_call_id") or "")
        if call_id and _holds_call(messages, call_id):
            messages.append(restored)
            continue
        name = str(restored.get("name") or "")
        output = restored.get("content")
        messages.append({
            "role": "user",
            "content": f"{name} finished:\n{_text(output)}",
            "tool_call_id": call_id,
            "name": name,
            "output": output,
        })
    return messages


def _model_from_memory(content: str) -> dict[str, Any]:
    payload: Any = None
    if content.startswith("{"):
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = None
    turn = turn_from_payload(payload)
    if turn is None:
        return {"role": "assistant", "content": content}
    calls = _named_calls(turn)
    if calls:
        return _assistant_message(_assistant_blocks(turn, calls), turn)
    return _assistant_message(turn.text(), turn)


def _tool_from_memory(content: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(content) if content.startswith("{") else None
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("type") != "tool-result":
        return None
    message: dict[str, Any] = {
        "role": "tool",
        "content": payload.get("output"),
        "tool_call_id": str(payload.get("request_id") or ""),
    }
    if payload.get("name"):
        message["name"] = str(payload["name"])
    return message


def _holds_call(messages: list[dict[str, Any]], call_id: str) -> bool:
    """Whether the latest assistant message still holds this tool call."""

    for message in reversed(messages):
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


def _arguments(value: Any) -> dict[str, Any]:
    """Tool arguments. A JSON object that arrived as text is still that object."""

    if isinstance(value, str):
        try:
            value = json.loads(value) if value.strip() else {}
        except json.JSONDecodeError:
            return {}
    if isinstance(value, dict):
        return value
    return {}


def _queued_signals(raw: Any) -> list[dict[str, Any]] | None:
    """Signals the kernel returned instead of running the model. None for anything else."""

    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else None
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, dict) or raw.get("type") != "signals":
        return None
    items = raw.get("items")
    if not isinstance(items, list):
        return None
    return [item for item in items if isinstance(item, dict)]


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
