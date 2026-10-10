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
        return {"type": "input_text", "text": getattr(part, "text", "")}
    if kind == "thinking":
        extra = getattr(part, "extra", None) or {}
        return {"type": "reasoning", "thinking": getattr(part, "thinking", ""), **extra}
    if kind == "hint":
        hint = getattr(part, "hint", "")
        text = " ".join(str(item) for item in hint) if isinstance(hint, list) else str(hint)
        return {"type": "input_text", "text": text}
    if kind == "data":
        source = getattr(part, "source", None)
        media_type = getattr(source, "media_type", "application/octet-stream")
        if getattr(source, "type", None) == "url":
            return {"type": "input_image", "image_url": getattr(source, "url", "")}
        data = getattr(source, "data", "")
        return {
            "type": "input_image",
            "image_url": f"data:{media_type};base64,{data}",
        }
    if kind == "tool_call":
        return {
            "type": "function_call",
            "call_id": getattr(part, "id", ""),
            "name": getattr(part, "name", ""),
            "arguments": getattr(part, "input", ""),
        }
    if kind == "tool_result":
        return {
            "type": "function_call_output",
            "call_id": getattr(part, "id", ""),
            "output": getattr(part, "output", ""),
        }
    return part


def _content(content: Any) -> Any:
    if isinstance(content, list):
        return [_part(part) for part in content]
    return _part(content)


def format_messages(messages: Any) -> list[Any]:
    if messages is None:
        return []
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]
    if isinstance(messages, dict):
        messages = [messages]
    result: list[Any] = []
    pending: list[Any] = []

    def flush() -> None:
        if not pending:
            return
        result.append({"role": "user", "content": [_part(part) for part in pending]})
        pending.clear()

    for item in messages:
        if isinstance(item, dict) and (
            "role" in item or item.get("type") in {"function_call", "function_call_output"}
        ):
            flush()
            message = dict(item)
            if "content" in message:
                message["content"] = _content(message["content"])
            result.append(message)
            continue
        converted = _part(item)
        if isinstance(converted, dict) and converted.get("type") in {
            "function_call",
            "function_call_output",
        }:
            flush()
            result.append(converted)
            continue
        pending.append(item)
    flush()
    return result


def parse_response(result: Any) -> str | None:
    output_text = getattr(result, "output_text", None)
    if output_text:
        return str(output_text)
    return None


def parse_response_turn(result: Any) -> dict[str, Any] | None:
    blocks: list[dict[str, Any]] = []
    output_text = getattr(result, "output_text", None)
    if output_text:
        blocks.append({"type": "text", "text": str(output_text)})
    for item in getattr(result, "output", None) or ():
        if getattr(item, "type", None) != "function_call":
            continue
        blocks.append(
            {
                "type": "tool-call",
                "name": str(getattr(item, "name", "") or ""),
                "arguments": getattr(item, "arguments", ""),
            }
        )
    return {
        "type": "model_turn",
        "blocks": blocks,
        "finish_reason": "stop",
    }


def parse_stream_chunk(chunk: Any) -> str:
    delta = getattr(chunk, "delta", None)
    if isinstance(delta, str) and delta:
        return delta
    text = getattr(delta, "text", None) if delta is not None else None
    if text:
        return str(text)
    return ""


def parse_stream_parts(chunk: Any) -> list[dict[str, Any]]:
    kind = getattr(chunk, "type", None)
    if kind in {"response.output_text.delta", "response.output_text.done"}:
        text = getattr(chunk, "delta", None) or getattr(chunk, "text", None)
        return [{"type": "text-delta", "text": str(text)}] if text else []
    if kind == "response.function_call_arguments.delta":
        fragment = getattr(chunk, "delta", None) or ""
        return [
            {
                "type": "tool-call-delta",
                "index": 0,
                "name": getattr(chunk, "name", None),
                "arguments": str(fragment),
            }
        ]
    if kind == "response.completed":
        return [{"type": "finish", "reason": "stop"}]
    return []


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
        kwargs["max_output_tokens"] = params["max_tokens"]
    if params.get("thinking_enable") is True and not _omit(params.get("reasoning_effort")):
        kwargs["reasoning_effort"] = params["reasoning_effort"]
    if params.get("parallel_tool_calls") is False:
        kwargs["parallel_tool_calls"] = False
    if not _omit(params.get("tools")):
        kwargs["tools"] = params["tools"]
    if not _omit(params.get("tool_choice")):
        kwargs["tool_choice"] = params["tool_choice"]
    if stream:
        kwargs["stream_options"] = {"include_usage": True}
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
        items = request.get("input_items")
        if items is None:
            items = format_messages(request.get("messages") or [])
        return await client.responses.create(
            model=request["model"],
            input=items,
            stream=stream,
            **_request_kwargs(
                request.get("parameters"),
                stream,
                request.get("generate_kwargs"),
                request.get("extra_body"),
            ),
        )

    return await _with_recovery(payload, send)
