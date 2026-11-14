"""Two tasks in one Linope window.

The window, its model slot, and the handoff in ``begin_wait`` are the kernel's.
This file only supplies the shared prompt, the shared tool, and the clock.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from queue import Empty, Queue
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from capability.agent_loop.linope.loop import CommandResult, Loop
from example.utilization.common import (
    HERE,
    RUNS,
    append_event,
    fingerprint,
    openai_tools,
    prompt_text,
    tasks_for,
)
from example.utilization.proxy import Proxy, completion_to_turn, post_chat
from kernel.command.events import CollectingEventSink
from kernel.command.process.clerk import KernelRuntime
from kernel.thread.task import close_process_threads


TOOL_PID = 20


class LoopSeat:
    """One Linope loop speaking the process protocol the window already drives."""

    def __init__(self, pid: int, task_id: str, log_path: Path) -> None:
        self.pid = pid
        self.task_id = task_id
        self.log_path = log_path
        self.is_alive = True
        self.activation = SimpleNamespace(
            pid=pid,
            grants=(),
            definition=SimpleNamespace(instance_id="agent_loop"),
            settings={},
        )
        catalog = {"wait_read": {"schemas": json.loads((HERE / "tools.json").read_text(encoding="utf-8"))}}
        self.loop = Loop(
            {"model": "model.openai_chat_model", "tools": ["wait_read"]},
            self._unused,
            catalog=catalog,
            identity=prompt_text(),
        )
        self.loop.bind(pid)
        self.loop._model_ready = True
        self.loop._pids["wait_read"] = TOOL_PID
        self._box: Queue[dict[str, Any]] = Queue()

    def begin_exchange(self, message: dict[str, Any], on_notice: object = None, *, wait: float | None = None) -> bool:
        del on_notice, wait
        body = message.get("body")
        self.loop.prepare(body if isinstance(body, str) else json.dumps(body, ensure_ascii=False))
        self._emit_step()
        return True

    def next_line(self, timeout: float | None) -> dict[str, Any] | None:
        try:
            if timeout:
                return self._box.get(timeout=timeout)
            return self._box.get_nowait()
        except Empty:
            return None

    def reply_command(self, result: Any = "", error: str = "", thread: str = "") -> None:
        del thread
        if error:
            self._box.put({"event": "error", "error": error})
            return
        try:
            done = self.loop.land(CommandResult(result=result))
        except Exception as exc:
            self._box.put({"event": "error", "error": str(exc)})
            return
        if done is not None:
            append_event(self.log_path, {
                "kind": "task_finished",
                "task": self.task_id,
                "t": time.time(),
            })
            self._box.put({"event": "result", "result": done})
            return
        self._emit_step()

    def end_exchange(self) -> None:
        return None

    def _emit_step(self) -> None:
        step = self.loop.step()
        self._box.put({
            "event": "command",
            "thread": step.get("thread") or "",
            "pc": step.get("pc") or "",
            "line": step.get("line") or "",
        })

    def _unused(self, line: str) -> CommandResult:
        if line.startswith("show "):
            return CommandResult(error="This experiment keeps no session page")
        raise RuntimeError(f"The window runs this command: {line}")


def _seat(pid: int, name: str, *, slot: str = "") -> SimpleNamespace:
    settings = {"slot": slot} if slot else {}
    return SimpleNamespace(
        pid=pid,
        is_alive=True,
        activation=SimpleNamespace(
            pid=pid,
            grants=(),
            definition=SimpleNamespace(instance_id=name),
            settings=settings,
        ),
    )


def _openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Linope stores tool calls as blocks. The chat API expects tool_calls."""

    converted: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role == "assistant" and isinstance(content, list):
            texts: list[str] = []
            calls: list[dict[str, Any]] = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and block.get("text"):
                    texts.append(str(block["text"]))
                elif block.get("type") == "tool-call":
                    arguments = block.get("arguments")
                    if not isinstance(arguments, str):
                        arguments = json.dumps(arguments or {}, ensure_ascii=False)
                    calls.append({
                        "id": str(block.get("id") or "call"),
                        "type": "function",
                        "function": {
                            "name": str(block.get("name") or ""),
                            "arguments": arguments,
                        },
                    })
            item: dict[str, Any] = {"role": "assistant", "content": "\n".join(texts)}
            if calls:
                item["tool_calls"] = calls
            reasoning = message.get("reasoning_content")
            if reasoning:
                item["reasoning_content"] = reasoning
            converted.append(item)
            continue
        if role == "tool":
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            converted.append({
                "role": "tool",
                "tool_call_id": str(message.get("tool_call_id") or ""),
                "content": text,
            })
            continue
        converted.append(message)
    return converted


def _task_id(payload: dict[str, Any]) -> str:
    for message in reversed(payload.get("messages") or []):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        for line in str(message.get("content") or "").splitlines():
            if line.startswith("task: "):
                return line.split("task: ", 1)[1].strip()
    return ""


def _run_tool(arguments: dict[str, Any]) -> str:
    completed = subprocess.run(
        [
            sys.executable,
            str(HERE / "slow_read.py"),
            "--path",
            str(arguments.get("path") or ""),
            "--seconds",
            str(arguments.get("seconds") or 0),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return completed.stderr or completed.stdout
    return completed.stdout


def _execute(line: str, base_url: str, model: str, api_key: str) -> Any:
    marker = " -- "
    if marker not in line:
        raise RuntimeError(f"Unreadable command: {line}")
    head, raw = line.split(marker, 1)
    body = json.loads(raw)
    if head.startswith("model run"):
        payload = post_chat(
            base_url,
            {
                "model": model,
                "temperature": 0,
                "messages": _openai_messages(body.get("messages") or []),
                "tools": openai_tools(body.get("tools")),
            },
            task_id=_task_id(body),
            api_key=api_key,
        )
        return completion_to_turn(payload)
    if head.startswith("load tool"):
        if isinstance(body, str):
            body = json.loads(body)
        return _run_tool(body)
    raise RuntimeError(f"Unreadable command: {line}")


def run(
    *,
    group: str,
    nonce: str,
    seconds: float,
    log_path: Path,
    base_url: str,
    model: str,
    api_key: str = "",
) -> None:
    tasks = tasks_for(group, seconds, nonce)
    if log_path.exists():
        log_path.unlink()
    append_event(log_path, {
        "kind": "round",
        "arm": "linope",
        "group": group,
        "nonce": nonce,
        "fingerprint": fingerprint(),
        "t": time.time(),
    })
    seats = [LoopSeat(41, tasks[0]["id"], log_path), LoopSeat(42, tasks[1]["id"], log_path)]
    sink = CollectingEventSink()
    clerk = KernelRuntime(sink)
    clerk._items.extend([
        ("agent_loop", seats[0]),
        ("agent_loop", seats[1]),
        ("wait_read", _seat(TOOL_PID, "wait_read")),
    ])
    clerk.drive.model.run = lambda body, **_kwargs: _execute(
        f"model run -- {json.dumps(body, ensure_ascii=False)}",
        base_url,
        model,
        api_key,
    )
    append_event(log_path, {"kind": "tasks_submitted", "t": time.time()})
    try:
        code = clerk.serve(lines=[
            f"load message 41 -- {tasks[0]['text']}",
            f"load message 42 -- {tasks[1]['text']}",
            "exit",
        ])
    finally:
        close_process_threads(41)
        close_process_threads(42)
    if code != 0:
        raise RuntimeError(f"Linope window exited {code}")
    failed = [event for event in sink.events if event.kind == "command.failed"]
    if failed:
        raise RuntimeError(failed[-1].data.get("error", {}).get("message") or "command failed")
    finished = [event for event in sink.events if event.kind == "turn.completed"]
    errors = [
        str((event.data.get("error") or {}).get("message") or "")
        for event in finished
        if event.data.get("error")
    ]
    if errors:
        raise RuntimeError(errors[0])
    if len(finished) < 2:
        details = [(event.kind, event.data) for event in sink.events]
        raise RuntimeError(f"The window finished {len(finished)} turns: {details}")


def _api_key() -> str:
    found = os.environ.get("OPENAI_API_KEY", "")
    if found:
        return found
    env_file = HERE.parents[1] / ".env"
    if not env_file.is_file():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1]
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group", choices=("mechanism", "real"), required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--seconds", type=float, default=0)
    parser.add_argument("--log", required=True)
    parser.add_argument("--model", default=os.environ.get("UTILIZATION_MODEL", "deepseek-flash"))
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--upstream", default=os.environ.get("UTILIZATION_UPSTREAM", ""))
    parser.add_argument("--mock-seconds", type=float, default=0.05)
    parser.add_argument("--proxy", default="")
    args = parser.parse_args(argv)
    owned: Proxy | None = None
    base_url = args.proxy
    if not base_url:
        owned = Proxy(
            Path(args.log),
            mock=args.mock,
            upstream=args.upstream,
            mock_seconds=args.mock_seconds,
        )
        base_url = owned.start()
    try:
        run(
            group=args.group,
            nonce=args.nonce,
            seconds=args.seconds,
            log_path=Path(args.log),
            base_url=base_url,
            model=args.model,
            api_key=_api_key(),
        )
    finally:
        if owned is not None:
            owned.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
