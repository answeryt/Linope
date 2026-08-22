# -*- coding: utf-8 -*-
"""Agent loop as a service handler: one task in, many turns, events out.

Inject call_model / call_tool / emit. A missing call_model echoes the user
message so the worker can run without a provider. Host must not split each
model turn into its own queue message.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any, Awaitable


PLUGIN_NAME = "kernel_agent_loop"
PLUGIN_VERSION = "1.0"

ModelHandler = Callable[..., Any | Awaitable[Any]]
ToolHandler = Callable[..., Any | Awaitable[Any]]
EmitHandler = Callable[[Mapping[str, Any]], Any | Awaitable[Any]]


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


async def run_agent_loop(
    task: Mapping[str, Any],
    *,
    call_model: ModelHandler | None = None,
    call_tool: ToolHandler | None = None,
    emit: EmitHandler | None = None,
    max_turns: int = 16,
) -> dict[str, Any]:
    """Run one agent session. Yields nothing; events go through emit."""
    task_id = task.get("task_id")
    user_message = str(task.get("user_message") or "")
    tools = task.get("tools") or ()
    model = call_model or _echo_model

    await _call(emit, {"type": "started", "task_id": task_id})
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    content = ""

    for _turn in range(max(1, max_turns)):
        response = await _call(model, messages, tools=tools) or {}
        tool_calls = list(response.get("tool_calls") or ())
        content = str(response.get("content") or "")
        if content:
            await _call(
                emit,
                {"type": "text.delta", "task_id": task_id, "content": content},
            )
        if not tool_calls:
            break
        messages.append(
            {"role": "assistant", "content": content, "tool_calls": tool_calls}
        )
        for call in tool_calls:
            name = str(call.get("name") or "")
            arguments = call.get("arguments") or {}
            await _call(
                emit,
                {
                    "type": "tool.call",
                    "task_id": task_id,
                    "name": name,
                    "arguments": arguments,
                },
            )
            tool_result = await _call(call_tool, name, arguments)
            tool_text = "" if tool_result is None else str(tool_result)
            await _call(
                emit,
                {
                    "type": "tool.result",
                    "task_id": task_id,
                    "name": name,
                    "content": tool_text,
                },
            )
            messages.append({"role": "tool", "name": name, "content": tool_text})

    await _call(emit, {"type": "done", "task_id": task_id, "content": content})
    return {
        "task_id": task_id,
        "session_id": task.get("session_id"),
        "status": "done",
        "content": content,
    }


async def iter_agent_loop(
    task: Mapping[str, Any],
    **kwargs: Any,
) -> AsyncIterator[dict[str, Any]]:
    """Same loop, but collect emit payloads for callers that want an iterator."""
    events: list[dict[str, Any]] = []

    async def _collect(event: Mapping[str, Any]) -> None:
        events.append(dict(event))
        emit = kwargs.get("emit")
        if emit is not None:
            await _call(emit, event)

    extra = dict(kwargs)
    extra["emit"] = _collect
    await run_agent_loop(task, **extra)
    for event in events:
        yield event
