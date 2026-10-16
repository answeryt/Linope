from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

MAX_RECOVERIES = 4
_PARAM_CACHE: dict[str, Any] = {}


def _omit(value: object) -> bool:
    return value is None or value == "UNSET"


def _param_leaf(folder: str, filename: str) -> Any:
    key = f"{folder}/{filename}"
    cached = _PARAM_CACHE.get(key)
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parents[1] / "model_paramaters" / folder / filename
    spec = importlib.util.spec_from_file_location(
        f"linope_{Path(__file__).stem}_{folder}",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _PARAM_CACHE[key] = module
    return module


def _vendor_role(role: object) -> str:
    return _param_leaf_sibling("roles.py").vendor_role(role)


def _param_leaf_sibling(filename: str) -> Any:
    cached = _PARAM_CACHE.get(filename)
    if cached is not None:
        return cached
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(f"linope_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _PARAM_CACHE[filename] = module
    return module


async def _with_recovery(payload: dict[str, Any], send: Any) -> Any:
    limits = _param_leaf("context_limits", "context_limits.py")
    request = dict(payload)
    if not isinstance(request.get("context_length"), int):
        request["context_length"] = limits.resolve_default_context_length(
            str(request.get("model") or "")
        )
    last_error: Exception | None = None
    for _ in range(1 + MAX_RECOVERIES):
        try:
            return await send(request)
        except Exception as err:
            last_error = err
            recovered = limits.recover_request(err, request)
            if recovered is None:
                raise
            request = recovered
    assert last_error is not None
    raise last_error


def _part(part: Any) -> Any:
    if isinstance(part, (dict, str)):
        return part
    kind = getattr(part, "type", None)
    if kind == "text":
        return {"type": "text", "text": getattr(part, "text", "")}
    if kind == "thinking":
        extra = getattr(part, "extra", None) or {}
        return {"type": "thinking", "thinking": getattr(part, "thinking", ""), **extra}
    if kind == "hint":
        hint = getattr(part, "hint", "")
        if isinstance(hint, list):
            return {"type": "text", "text": " ".join(str(item) for item in hint)}
        return {"type": "text", "text": str(hint)}
    if kind == "data":
        source = getattr(part, "source", None)
        media_type = getattr(source, "media_type", "application/octet-stream")
        if getattr(source, "type", None) == "url":
            return {
                "type": "image_url",
                "image_url": {"url": getattr(source, "url", "")},
                "media_type": media_type,
            }
        data = getattr(source, "data", "")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{data}"},
            "media_type": media_type,
        }
    if kind == "tool_call":
        return {
            "type": "function",
            "id": getattr(part, "id", ""),
            "function": {
                "name": getattr(part, "name", ""),
                "arguments": getattr(part, "input", ""),
            },
        }
    if kind == "tool_result":
        return {
            "role": "tool",
            "tool_call_id": getattr(part, "id", ""),
            "content": getattr(part, "output", ""),
        }
    return part


def _content(content: Any) -> Any:
    if isinstance(content, list):
        return [_part(part) for part in content]
    return _part(content)


def format_messages(messages: Any) -> list[dict[str, Any]]:
    if messages is None:
        return []
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]
    if isinstance(messages, dict):
        messages = [messages]
    result: list[dict[str, Any]] = []
    pending: list[Any] = []

    def flush() -> None:
        if not pending:
            return
        result.append({"role": "user", "content": [_part(part) for part in pending]})
        pending.clear()

    for item in messages:
        if isinstance(item, dict) and "role" in item:
            flush()
            message = dict(item)
            message["role"] = _vendor_role(message.get("role"))
            if "content" in message:
                converted = _content(message["content"])
                message["content"] = "" if converted is None else converted
            result.append(_promote_tool_calls(message))
            continue
        converted = _part(item)
        if isinstance(converted, dict) and converted.get("role") == "tool":
            flush()
            result.append(converted)
            continue
        pending.append(item)
    flush()
    return result


def parse_response(result: Any) -> str | None:
    choices = getattr(result, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        if message is not None:
            content = getattr(message, "content", None)
            if content:
                return str(content)
    return None


def parse_response_turn(result: Any) -> dict[str, Any] | None:
    choices = getattr(result, "choices", None)
    if not choices:
        return None
    choice = choices[0]
    message = getattr(choice, "message", None)
    if message is None:
        return None
    blocks: list[dict[str, Any]] = []
    content = getattr(message, "content", None)
    if content:
        blocks.append({"type": "text", "text": str(content)})
    for call in getattr(message, "tool_calls", None) or ():
        function = getattr(call, "function", None)
        if function is None:
            continue
        blocks.append(
            {
                "type": "tool-call",
                "id": str(getattr(call, "id", "") or ""),
                "name": str(getattr(function, "name", "") or ""),
                "arguments": getattr(function, "arguments", ""),
            }
        )
    payload = {
        "type": "model_turn",
        "blocks": blocks,
        "finish_reason": str(getattr(choice, "finish_reason", None) or "stop"),
    }
    from capability.model.model_runtime.usage import read_usage

    usage = read_usage(getattr(result, "usage", None))
    if usage:
        payload["usage"] = usage
    return payload


def parse_stream_chunk(chunk: Any) -> str:
    choices = getattr(chunk, "choices", None)
    if not choices:
        return ""
    delta = getattr(choices[0], "delta", None)
    content = getattr(delta, "content", None) if delta is not None else None
    return str(content) if content else ""


def parse_stream_parts(chunk: Any) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for choice in getattr(chunk, "choices", None) or ():
        delta = getattr(choice, "delta", None)
        content = getattr(delta, "content", None) if delta is not None else None
        if content:
            parts.append({"type": "text-delta", "text": str(content)})
        for call in getattr(delta, "tool_calls", None) or ():
            function = getattr(call, "function", None)
            if function is None:
                continue
            parts.append(
                {
                    "type": "tool-call-delta",
                    "index": int(getattr(call, "index", 0) or 0),
                    "id": getattr(call, "id", None),
                    "name": getattr(function, "name", None),
                    "arguments": getattr(function, "arguments", "") or "",
                }
            )
        finish = getattr(choice, "finish_reason", None)
        if finish:
            parts.append({"type": "finish", "reason": str(finish)})
    from capability.model.model_runtime.usage import read_usage, usage_part

    part = usage_part(read_usage(getattr(chunk, "usage", None)))
    if part is not None:
        parts.append(part)
    return parts


def _promote_tool_calls(message: dict[str, Any]) -> dict[str, Any]:
    """Turn provider-neutral tool blocks into chat-completions tool_calls."""
    content = message.get("content")
    if not isinstance(content, list) or message.get("role") != "assistant":
        return message
    calls = [part for part in content if isinstance(part, dict) and part.get("type") == "tool-call"]
    if not calls:
        return message
    texts = [
        str(part.get("text") or "")
        for part in content
        if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
    ]
    message["content"] = "\n".join(texts)
    message["tool_calls"] = [
        {
            "id": str(part.get("id") or ""),
            "type": "function",
            "function": {
                "name": str(part.get("name") or ""),
                "arguments": _argument_text(part.get("arguments")),
            },
        }
        for part in calls
    ]
    return message


def _argument_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    import json
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _function_tools(value: Any) -> list[dict[str, Any]]:
    """Normalize kernel tool schemas to OpenAI Chat function tools."""
    if value is None or value == "UNSET":
        return []
    raw = value if isinstance(value, list) else [value]
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function" and isinstance(item.get("function"), dict):
            normalized.append(item)
            continue
        name = item.get("name")
        if not name:
            continue
        normalized.append(
            {
                "type": "function",
                "function": {
                    "name": str(name),
                    "description": str(item.get("description") or ""),
                    "parameters": item.get("parameters")
                    or {"type": "object", "properties": {}},
                },
            }
        )
    return normalized


def _request_kwargs(
    parameters: dict[str, Any] | None,
    stream: bool,
    generate_kwargs: dict[str, Any] | None,
    extra_body: dict[str, Any] | None,
) -> dict[str, Any]:
    params = parameters or {}
    kwargs: dict[str, Any] = {}
    if not _omit(params.get("temperature")):
        kwargs["temperature"] = params["temperature"]
    if not _omit(params.get("top_p")):
        kwargs["top_p"] = params["top_p"]
    if not _omit(params.get("max_tokens")):
        kwargs["max_completion_tokens"] = params["max_tokens"]
    if params.get("thinking_enable") is True and not _omit(params.get("reasoning_effort")):
        kwargs["reasoning_effort"] = params["reasoning_effort"]
    if params.get("parallel_tool_calls") is False:
        kwargs["parallel_tool_calls"] = False
    tools = _function_tools(params.get("tools"))
    if tools:
        kwargs["tools"] = tools
        if not _omit(params.get("tool_choice")):
            kwargs["tool_choice"] = params["tool_choice"]
    if stream:
        kwargs["stream_options"] = {"include_usage": True}
    if not _omit(params.get("voice")):
        kwargs["modalities"] = ["text", "audio"]
        kwargs["audio"] = {"voice": params["voice"], "format": "pcm16"}
    if generate_kwargs:
        kwargs.update(generate_kwargs)
    if extra_body:
        kwargs["extra_body"] = {**extra_body, **kwargs.get("extra_body", {})}
    return kwargs


async def call_api(payload: dict[str, Any]) -> Any:
    import importlib

    openai = importlib.import_module("openai")

    async def send(request: dict[str, Any]) -> Any:
        stream = request.get("stream") is True
        client = openai.AsyncClient(
            api_key=request["api_key"],
            organization=request.get("organization"),
            base_url=request.get("base_url"),
            **(request.get("client_kwargs") or {}),
        )
        return await client.chat.completions.create(
            model=request["model"],
            messages=format_messages(request.get("messages") or []),
            stream=stream,
            **_request_kwargs(
                request.get("parameters"),
                stream,
                request.get("generate_kwargs"),
                request.get("extra_body"),
            ),
        )

    return await _with_recovery(payload, send)
