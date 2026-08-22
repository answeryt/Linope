# -*- coding: utf-8 -*-
"""Turn agent events into LLM / tool / done events.

This replaces ``for turn: think(); act()``. call_model / call_tool / emit
are injected. Host must not split each model turn into its own service
queue message.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, MutableMapping
from typing import Any


PLUGIN_NAME = "kernel_async_dispatch"
PLUGIN_VERSION = "1.0"

ASYNC_IO = "async_io"

USER_MESSAGE = "user.message"
LLM_CALL = "llm.call"
LLM_RESPONSE = "llm.response"
TOOL_CALL = "tool.call"
TOOL_RESULT = "tool.result"
TASK_DONE = "task.done"
HUMAN_WAIT = "human.wait"
HUMAN_RESUME = "human.resume"

ModelHandler = Callable[..., Any]
ToolHandler = Callable[..., Any]
EmitHandler = Callable[..., Any]
GatherHandler = Callable[..., Any]
ClassifyHandler = Callable[..., Any]


async def _call(func: Callable[..., Any] | None, *args: Any, **kwargs: Any) -> Any:
    if func is None:
        return None
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


async def _echo_model(messages: list[dict[str, Any]], tools: Any = None) -> dict[str, Any]:
    last = ""
    for item in reversed(messages):
        if item.get("role") == "user":
            last = str(item.get("content") or "")
            break
    return {"content": last, "tool_calls": []}


def _session_key(event: Mapping[str, Any]) -> str:
    for key in ("execution_id", "task_id", "process_id"):
        value = event.get(key)
        if value:
            return str(value)
    return "_default"


class AgentDispatch:
    """Event handler: user/llm/tool/human → the next event."""

    def __init__(
        self,
        *,
        call_model: ModelHandler | None = None,
        call_tool: ToolHandler | None = None,
        emit: EmitHandler | None = None,
        gather: GatherHandler | None = None,
        classify: ClassifyHandler | None = None,
        max_turns: int = 16,
    ) -> None:
        self.call_model = call_model or _echo_model
        self.call_tool = call_tool
        self.emit = emit
        self.gather = gather
        self.classify = classify
        self.max_turns = max(1, max_turns)
        self._sessions: dict[str, dict[str, Any]] = {}

    def _state(self, event: Mapping[str, Any]) -> dict[str, Any]:
        key = _session_key(event)
        session = self._sessions.get(key)
        if session is None:
            session = {
                "messages": [],
                "pending_tools": 0,
                "turns": 0,
                "content": "",
                "done": False,
            }
            self._sessions[key] = session
        return session

    async def __call__(self, event: Mapping[str, Any], loop: Any = None) -> None:
        await self.dispatch(event, loop=loop)

    async def dispatch(self, event: Mapping[str, Any], loop: Any = None) -> None:
        kind = str(event.get("type") or "")
        if kind == USER_MESSAGE:
            await self._on_user(event, loop)
        elif kind == LLM_CALL:
            await self._on_llm_call(event, loop)
        elif kind == LLM_RESPONSE:
            await self._on_llm_response(event, loop)
        elif kind == TOOL_CALL:
            await self._on_tool_call(event, loop)
        elif kind == TOOL_RESULT:
            await self._on_tool_result(event, loop)
        elif kind == HUMAN_RESUME:
            await self._on_human_resume(event, loop)
        elif kind == HUMAN_WAIT:
            return
        elif kind == TASK_DONE:
            self._state(event)["done"] = True

    async def _publish(
        self,
        event: Mapping[str, Any],
        event_type: str,
        loop: Any,
        **fields: Any,
    ) -> None:
        payload: MutableMapping[str, Any] = {
            "type": event_type,
            "task_id": event.get("task_id"),
            "process_id": event.get("process_id"),
            "execution_id": event.get("execution_id"),
            "thread_id": event.get("thread_id"),
        }
        payload.update(fields)
        loop_emit = getattr(loop, "emit", None) if loop is not None else None
        if callable(loop_emit):
            await _call(loop_emit, payload)
            if self.emit is not None and self.emit is not loop_emit:
                await _call(self.emit, payload)
            return
        if self.emit is not None:
            await _call(self.emit, payload)

    async def _on_user(self, event: Mapping[str, Any], loop: Any) -> None:
        session = self._state(event)
        content = str(event.get("content") or event.get("user_message") or "")
        session["messages"].append({"role": "user", "content": content})
        await self._publish(event, LLM_CALL, loop, tools=event.get("tools") or ())

    async def _on_llm_call(self, event: Mapping[str, Any], loop: Any) -> None:
        session = self._state(event)
        if session["turns"] >= self.max_turns:
            await self._publish(event, TASK_DONE, loop, content=session["content"], status="max_turns")
            session["done"] = True
            return
        session["turns"] += 1
        response = await _call(
            self.call_model,
            session["messages"],
            tools=event.get("tools"),
        ) or {}
        await self._publish(
            event,
            LLM_RESPONSE,
            loop,
            content=str(response.get("content") or ""),
            tool_calls=list(response.get("tool_calls") or ()),
        )

    async def _on_llm_response(self, event: Mapping[str, Any], loop: Any) -> None:
        session = self._state(event)
        content = str(event.get("content") or "")
        tool_calls = list(event.get("tool_calls") or ())
        if content:
            session["content"] = content
        if not tool_calls:
            session["messages"].append({"role": "assistant", "content": content})
            session["done"] = True
            await self._publish(event, TASK_DONE, loop, content=content, status="done")
            return
        session["messages"].append(
            {"role": "assistant", "content": content, "tool_calls": tool_calls}
        )
        session["pending_tools"] = len(tool_calls)
        calls = [self._publish_tool(event, loop, call) for call in tool_calls]
        if self.gather is not None and len(calls) > 1:
            await _call(self.gather, *calls)
        else:
            for call in calls:
                await call

    async def _publish_tool(
        self,
        event: Mapping[str, Any],
        loop: Any,
        call: Mapping[str, Any],
    ) -> None:
        name = str(call.get("name") or "")
        arguments = call.get("arguments") or {}
        lane = ASYNC_IO
        if self.classify is not None:
            lane = await _call(self.classify, call) or ASYNC_IO
        await self._publish(
            event,
            TOOL_CALL,
            loop,
            name=name,
            arguments=arguments,
            resource=lane,
        )

    async def _on_tool_call(self, event: Mapping[str, Any], loop: Any) -> None:
        name = str(event.get("name") or "")
        arguments = event.get("arguments") or {}
        result = await _call(self.call_tool, name, arguments)
        text = "" if result is None else str(result)
        await self._publish(event, TOOL_RESULT, loop, name=name, content=text)

    async def _on_tool_result(self, event: Mapping[str, Any], loop: Any) -> None:
        session = self._state(event)
        name = str(event.get("name") or "")
        text = str(event.get("content") or "")
        session["messages"].append({"role": "tool", "name": name, "content": text})
        pending = max(0, int(session.get("pending_tools") or 0) - 1)
        session["pending_tools"] = pending
        if pending == 0 and not session.get("done"):
            await self._publish(event, LLM_CALL, loop)

    async def _on_human_resume(self, event: Mapping[str, Any], loop: Any) -> None:
        session = self._state(event)
        note = str(event.get("content") or "")
        if note:
            session["messages"].append({"role": "user", "content": note})
        await self._publish(event, LLM_CALL, loop, tools=event.get("tools") or ())

