# -*- coding: utf-8 -*-
"""Normalize provider function-calling payloads into kernel tool_calls.

Host injects ``FunctionCallAdapter`` as ``call_model``. This file must not
import kernel or model siblings. SDK objects are read by field name only.

Kernel contract::

    {"content": str, "tool_calls": [{"name": str, "arguments": dict, "id": str}]}
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping
from typing import Any


PLUGIN_NAME = "adapter_function_call"
PLUGIN_VERSION = "1.0"

OPENAI_CHAT = "openai_chat"
OPENAI_RESPONSE = "openai_response"
ANTHROPIC = "anthropic"
GEMINI = "gemini"
KERNEL = "kernel"

CONTENT = "content"
TOOL_CALLS = "tool_calls"
NAME = "name"
ARGUMENTS = "arguments"
CALL_ID = "id"

_BLOCK_TYPES = frozenset(
    {
        "text",
        "tool_use",
        "tool_result",
        "tool_call",
        "function_call",
        "output_text",
        "image",
        "reasoning",
        "message",
    }
)


def normalize_response(response: Any) -> dict[str, Any]:
    """Turn an OpenAI / Anthropic / Gemini / kernel payload into kernel IR."""
    if response is None:
        return {CONTENT: "", TOOL_CALLS: []}
    if isinstance(response, str):
        return {CONTENT: response, TOOL_CALLS: []}

    choices = _field(response, "choices")
    if choices:
        message = _field(_first(choices), "message", "delta")
        if message is not None:
            return _from_chat_message(message)

    output = _field(response, "output")
    if output and _looks_like_responses(output):
        return _from_responses_output(output)

    candidates = _field(response, "candidates")
    if candidates:
        return _from_gemini_content(_field(_first(candidates), CONTENT))

    body = _field(response, CONTENT)
    native_calls = _field(response, TOOL_CALLS)
    legacy = _field(response, "function_call")
    if _is_block_list(body) and native_calls is None and legacy is None:
        return _from_content_blocks(body)

    parts = _field(response, "parts")
    if parts:
        return _from_gemini_content(response)

    if native_calls is not None or legacy is not None:
        return _from_chat_message(response)

    return {CONTENT: _text_of(body), TOOL_CALLS: []}


def normalize_tool_call(call: Any, *, index: int = 0) -> dict[str, Any]:
    """Flatten one native tool call into ``{name, arguments, id}``."""
    nested = _field(call, "function")
    name = _field(nested, NAME) if nested is not None else None
    arguments = _field(nested, ARGUMENTS) if nested is not None else None
    if not name:
        name = _field(call, NAME)
    if arguments is None:
        arguments = _field(call, ARGUMENTS, "input", "args", "parameters")
    record = {
        NAME: str(name or ""),
        ARGUMENTS: _arguments(arguments),
        CALL_ID: str(
            _field(call, CALL_ID, "call_id", "tool_call_id", "toolUseId")
            or f"call_{index}"
        ),
    }
    return record


def encode_messages(
    messages: Any,
    *,
    dialect: str = OPENAI_CHAT,
) -> list[dict[str, Any]]:
    """Rewrite kernel session messages into a provider chat dialect."""
    kind = str(dialect or OPENAI_CHAT)
    encoded: list[dict[str, Any]] = []
    pending: list[tuple[str, str]] = []
    for message in _iter(messages):
        item = _mapping(message) or {}
        role = str(item.get("role") or "")
        calls = item.get(TOOL_CALLS)
        if role in {"assistant", "model"} and calls:
            normalized = [
                normalize_tool_call(call, index=index)
                for index, call in enumerate(_iter(calls))
            ]
            pending = [
                (str(call.get(CALL_ID) or f"call_{index}"), str(call.get(NAME) or ""))
                for index, call in enumerate(normalized)
            ]
            encoded.append(_encode_assistant(item, normalized, kind))
            continue
        if role in {"tool", "function"}:
            encoded.append(_encode_tool_result(item, pending, kind))
            continue
        encoded.append(_encode_plain(item, kind))
    return encoded


def encode_tools(tools: Any, *, dialect: str = OPENAI_CHAT) -> Any:
    """Rewrite tool schemas into a provider dialect. Already-native items pass through."""
    if tools is None:
        return None
    kind = str(dialect or OPENAI_CHAT)
    items = [_encode_one_tool(item, kind) for item in _iter(tools)]
    if kind == GEMINI:
        declarations = [
            item.get("function_declarations", [item])[0]
            if isinstance(item, Mapping) and "function_declarations" in item
            else item
            for item in items
        ]
        return [{"function_declarations": declarations}] if declarations else []
    return items


class FunctionCallAdapter:
    """Callable ``call_model`` wrapper. Kernel sees only the IR contract."""

    def __init__(
        self,
        call_model: Callable[..., Any] | None = None,
        *,
        dialect: str = OPENAI_CHAT,
    ) -> None:
        self.call_model = call_model
        self.dialect = str(dialect or OPENAI_CHAT)

    async def __call__(
        self,
        messages: list[dict[str, Any]],
        tools: Any = None,
    ) -> dict[str, Any]:
        return await self.complete(messages, tools=tools)

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Any = None,
    ) -> dict[str, Any]:
        if self.call_model is None:
            return _echo(messages)
        outbound = encode_messages(messages, dialect=self.dialect)
        encoded_tools = (
            encode_tools(tools, dialect=self.dialect) if tools is not None else tools
        )
        raw = await _call(self.call_model, outbound, tools=encoded_tools)
        return normalize_response(raw)


async def _call(func: Callable[..., Any] | None, *args: Any, **kwargs: Any) -> Any:
    if func is None:
        return None
    result = func(*args, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _echo(messages: list[dict[str, Any]]) -> dict[str, Any]:
    last = ""
    for item in reversed(messages or ()):
        mapping = _mapping(item) or {}
        if mapping.get("role") == "user":
            last = str(mapping.get(CONTENT) or "")
            break
    return {CONTENT: last, TOOL_CALLS: []}


def _from_chat_message(message: Any) -> dict[str, Any]:
    calls = [
        normalize_tool_call(call, index=index)
        for index, call in enumerate(_iter(_field(message, TOOL_CALLS)))
    ]
    legacy = _field(message, "function_call")
    if not calls and legacy is not None:
        calls = [normalize_tool_call(legacy, index=0)]
    return {CONTENT: _text_of(_field(message, CONTENT)), TOOL_CALLS: calls}


def _from_responses_output(output: Any) -> dict[str, Any]:
    texts: list[str] = []
    calls: list[dict[str, Any]] = []
    for item in _iter(output):
        kind = str(_field(item, "type") or "")
        if kind == "function_call" or _field(item, "call_id") is not None:
            calls.append(normalize_tool_call(item, index=len(calls)))
            continue
        inner = _field(item, CONTENT)
        if inner is not None:
            texts.append(_text_of(inner))
        else:
            texts.append(_text_of(item))
    return {CONTENT: "".join(texts), TOOL_CALLS: calls}


def _from_content_blocks(blocks: Any) -> dict[str, Any]:
    texts: list[str] = []
    calls: list[dict[str, Any]] = []
    for block in _iter(blocks):
        kind = str(_field(block, "type") or "")
        if kind in {"tool_use", "tool_call", "function_call"}:
            calls.append(normalize_tool_call(block, index=len(calls)))
            continue
        texts.append(_text_of(block))
    return {CONTENT: "".join(texts), TOOL_CALLS: calls}


def _from_gemini_content(content: Any) -> dict[str, Any]:
    texts: list[str] = []
    calls: list[dict[str, Any]] = []
    parts = _field(content, "parts")
    if parts is None:
        parts = content
    for part in _iter(parts):
        fn = _field(part, "functionCall", "function_call")
        if fn is not None:
            calls.append(normalize_tool_call(fn, index=len(calls)))
            continue
        text = _field(part, "text")
        if text:
            texts.append(str(text))
    return {CONTENT: "".join(texts), TOOL_CALLS: calls}


def _encode_assistant(
    message: Mapping[str, Any],
    calls: list[dict[str, Any]],
    dialect: str,
) -> dict[str, Any]:
    text = _text_of(message.get(CONTENT))
    if dialect == KERNEL:
        return {**dict(message), CONTENT: text, TOOL_CALLS: calls}
    if dialect == ANTHROPIC:
        blocks: list[dict[str, Any]] = []
        if text:
            blocks.append({"type": "text", "text": text})
        for call in calls:
            blocks.append(
                {
                    "type": "tool_use",
                    CALL_ID: call.get(CALL_ID),
                    NAME: call.get(NAME),
                    "input": dict(call.get(ARGUMENTS) or {}),
                }
            )
        return {"role": "assistant", CONTENT: blocks}
    if dialect == GEMINI:
        parts: list[dict[str, Any]] = []
        if text:
            parts.append({"text": text})
        for call in calls:
            parts.append(
                {
                    "functionCall": {
                        NAME: call.get(NAME),
                        "args": dict(call.get(ARGUMENTS) or {}),
                    }
                }
            )
        return {"role": "model", "parts": parts}
    if dialect == OPENAI_RESPONSE:
        items: list[dict[str, Any]] = []
        if text:
            items.append(
                {
                    "type": "message",
                    "role": "assistant",
                    CONTENT: [{"type": "output_text", "text": text}],
                }
            )
        for call in calls:
            items.append(
                {
                    "type": "function_call",
                    "call_id": call.get(CALL_ID),
                    NAME: call.get(NAME),
                    ARGUMENTS: json.dumps(call.get(ARGUMENTS) or {}, ensure_ascii=False),
                }
            )
        return {"role": "assistant", "output": items}
    openai_calls = [
        {
            CALL_ID: call.get(CALL_ID),
            "type": "function",
            "function": {
                NAME: call.get(NAME),
                ARGUMENTS: json.dumps(call.get(ARGUMENTS) or {}, ensure_ascii=False),
            },
        }
        for call in calls
    ]
    payload: dict[str, Any] = {"role": "assistant", CONTENT: text or None}
    if openai_calls:
        payload[TOOL_CALLS] = openai_calls
    return payload


def _encode_tool_result(
    message: Mapping[str, Any],
    pending: list[tuple[str, str]],
    dialect: str,
) -> dict[str, Any]:
    text = _text_of(message.get(CONTENT) or message.get("output"))
    name = str(message.get(NAME) or "")
    call_id = _take_id(message, pending)
    if dialect == KERNEL:
        return {"role": "tool", NAME: name, CONTENT: text, "tool_call_id": call_id}
    if dialect == ANTHROPIC:
        return {
            "role": "user",
            CONTENT: [
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    CONTENT: text,
                }
            ],
        }
    if dialect == GEMINI:
        return {
            "role": "user",
            "parts": [
                {
                    "functionResponse": {
                        NAME: name,
                        "response": {"result": text},
                    }
                }
            ],
        }
    if dialect == OPENAI_RESPONSE:
        return {
            "type": "function_call_output",
            "call_id": call_id,
            "output": text,
        }
    payload = {"role": "tool", "tool_call_id": call_id, CONTENT: text}
    if name:
        payload[NAME] = name
    return payload


def _encode_plain(message: Mapping[str, Any], dialect: str) -> dict[str, Any]:
    role = str(message.get("role") or "user")
    text = _text_of(message.get(CONTENT))
    if dialect == GEMINI:
        gemini_role = "model" if role == "assistant" else "user"
        return {"role": gemini_role, "parts": [{"text": text}]}
    if dialect == OPENAI_RESPONSE:
        return {
            "type": "message",
            "role": role,
            CONTENT: [{"type": "input_text", "text": text}],
        }
    return {"role": role, CONTENT: text}


def _encode_one_tool(item: Any, dialect: str) -> dict[str, Any]:
    payload = _mapping(item) or {}
    if dialect in {OPENAI_CHAT, OPENAI_RESPONSE}:
        nested = payload.get("function")
        if isinstance(nested, Mapping) and nested.get(NAME):
            return dict(payload)
        name = str(payload.get(NAME) or "")
        return {
            "type": "function",
            "function": {
                NAME: name,
                "description": payload.get("description") or "",
                "parameters": payload.get("parameters")
                or payload.get("input_schema")
                or {},
            },
        }
    if dialect == ANTHROPIC:
        if payload.get("input_schema") is not None:
            return dict(payload)
        nested = payload.get("function")
        source = nested if isinstance(nested, Mapping) else payload
        return {
            NAME: str(source.get(NAME) or payload.get(NAME) or ""),
            "description": source.get("description") or payload.get("description") or "",
            "input_schema": source.get("parameters") or payload.get("parameters") or {},
        }
    nested = payload.get("function")
    source = nested if isinstance(nested, Mapping) else payload
    return {
        NAME: str(source.get(NAME) or payload.get(NAME) or ""),
        "description": source.get("description") or "",
        "parameters": source.get("parameters") or payload.get("parameters") or {},
    }


def _take_id(message: Mapping[str, Any], pending: list[tuple[str, str]]) -> str:
    given = message.get("tool_call_id") or message.get(CALL_ID) or message.get("call_id")
    if given:
        text = str(given)
        for index, (call_id, _name) in enumerate(pending):
            if call_id == text:
                pending.pop(index)
                return text
        return text
    name = str(message.get(NAME) or "")
    if name:
        for index, (call_id, pending_name) in enumerate(pending):
            if pending_name == name:
                pending.pop(index)
                return call_id
    if pending:
        call_id, _name = pending.pop(0)
        return call_id
    return ""


def _arguments(value: Any) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    dumped = _dump(value)
    if dumped is not None:
        return dumped
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"_raw": value}
        if isinstance(parsed, Mapping):
            return dict(parsed)
        return {"value": parsed}
    return {}


def _text_of(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        text = value.get("text")
        if text is not None:
            return str(text)
        inner = value.get(CONTENT)
        if inner is not None and inner is not value:
            return _text_of(inner)
        return ""
    dumped = _dump(value)
    if dumped is not None:
        return _text_of(dumped)
    if isinstance(value, (list, tuple)):
        return "".join(_text_of(item) for item in value)
    return str(value)


def _is_block_list(value: Any) -> bool:
    items = _iter(value) if not isinstance(value, (str, bytes, Mapping)) else []
    if not items:
        return False
    kind = str(_field(items[0], "type") or "")
    return kind in _BLOCK_TYPES


def _looks_like_responses(output: Any) -> bool:
    first = _first(output)
    if first is None:
        return False
    kind = str(_field(first, "type") or "")
    return kind in _BLOCK_TYPES or _field(first, "call_id") is not None


def _field(obj: Any, *names: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        for name in names:
            if name in obj and obj[name] is not None:
                return obj[name]
        return None
    for name in names:
        if hasattr(obj, name):
            value = getattr(obj, name)
            if value is not None:
                return value
    dumped = _dump(obj)
    if dumped is None:
        return None
    for name in names:
        if name in dumped and dumped[name] is not None:
            return dumped[name]
    return None


def _mapping(obj: Any) -> dict[str, Any] | None:
    if obj is None:
        return None
    if isinstance(obj, Mapping):
        return dict(obj)
    dumped = _dump(obj)
    return dumped


def _dump(obj: Any) -> dict[str, Any] | None:
    for name in ("model_dump", "to_dict"):
        func = getattr(obj, name, None)
        if not callable(func):
            continue
        try:
            payload = func()
        except TypeError:
            continue
        if isinstance(payload, Mapping):
            return dict(payload)
    func = getattr(obj, "dict", None)
    if callable(func) and not isinstance(obj, type):
        try:
            payload = func()
        except TypeError:
            payload = None
        if isinstance(payload, Mapping):
            return dict(payload)
    return None


def _first(value: Any) -> Any:
    items = _iter(value)
    return items[0] if items else None


def _iter(value: Any) -> list[Any]:
    if value is None or value == ():
        return []
    if isinstance(value, (str, bytes, Mapping)):
        return [value]
    try:
        return list(value)
    except TypeError:
        return [value]
