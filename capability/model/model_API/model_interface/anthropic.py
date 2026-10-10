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
    if isinstance(part, str):
        return {"type": "text", "text": part}
    if isinstance(part, dict):
        return part
    kind = getattr(part, "type", None)
    if kind == "text":
        return {"type": "text", "text": getattr(part, "text", "")}
    if kind == "thinking":
        extra = getattr(part, "extra", None) or {}
        block = {"type": "thinking", "thinking": getattr(part, "thinking", "")}
        block.update(extra)
        return block
    if kind == "hint":
        hint = getattr(part, "hint", "")
        text = " ".join(str(item) for item in hint) if isinstance(hint, list) else str(hint)
        return {"type": "text", "text": text}
    if kind == "data":
        source = getattr(part, "source", None)
        media_type = getattr(source, "media_type", "application/octet-stream")
        if getattr(source, "type", None) == "url":
            return {
                "type": "image",
                "source": {"type": "url", "url": getattr(source, "url", "")},
            }
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": getattr(source, "data", ""),
            },
        }
    if kind == "tool_call":
        return {
            "type": "tool_use",
            "id": getattr(part, "id", ""),
            "name": getattr(part, "name", ""),
            "input": getattr(part, "input", ""),
        }
    if kind == "tool_result":
        return {
            "type": "tool_result",
            "tool_use_id": getattr(part, "id", ""),
            "content": getattr(part, "output", ""),
        }
    return part


def _content(content: Any) -> Any:
    if isinstance(content, str):
        return content
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
            role = item.get("role")
            if role == "system":
                result.append({"role": "user", "content": _content(item.get("content"))})
                continue
            message = {"role": role, "content": _content(item.get("content", item))}
            result.append(message)
            continue
        pending.append(item)
    flush()
    return result


def parse_response(result: Any) -> str | None:
    content = getattr(result, "content", None)
    if isinstance(content, list) and content:
        joined = "".join(str(getattr(block, "text", "") or "") for block in content)
        return joined or None
    return None


def parse_response_turn(result: Any) -> dict[str, Any] | None:
    blocks: list[dict[str, Any]] = []
    for block in getattr(result, "content", None) or ():
        kind = getattr(block, "type", None)
        if kind == "text":
            text = getattr(block, "text", "")
            if text:
                blocks.append({"type": "text", "text": str(text)})
        elif kind == "tool_use":
            blocks.append(
                {
                    "type": "tool-call",
                    "name": str(getattr(block, "name", "") or ""),
                    "arguments": getattr(block, "input", {}),
                }
            )
    return {
        "type": "model_turn",
        "blocks": blocks,
        "finish_reason": str(getattr(result, "stop_reason", None) or "stop"),
    }


def parse_stream_chunk(chunk: Any) -> str:
    if getattr(chunk, "type", None) != "content_block_delta":
        delta = getattr(chunk, "delta", None)
        text = getattr(delta, "text", None) if delta is not None else None
        return str(text) if text else ""
    delta = getattr(chunk, "delta", None)
    text = getattr(delta, "text", None) if delta is not None else None
    return str(text) if text else ""


def parse_stream_parts(chunk: Any) -> list[dict[str, Any]]:
    kind = getattr(chunk, "type", None)
    if kind == "content_block_delta":
        delta = getattr(chunk, "delta", None)
        delta_kind = getattr(delta, "type", None)
        if delta_kind == "text_delta":
            text = getattr(delta, "text", "")
            return [{"type": "text-delta", "text": str(text)}] if text else []
        if delta_kind == "input_json_delta":
            fragment = getattr(delta, "partial_json", "")
            return [
                {
                    "type": "tool-call-delta",
                    "index": 0,
                    "arguments": str(fragment),
                }
            ]
    if kind == "message_delta":
        delta = getattr(chunk, "delta", None)
        stop = getattr(delta, "stop_reason", None) if delta is not None else None
        return [{"type": "finish", "reason": str(stop)}] if stop else []
    return []


def _request_kwargs(
    parameters: dict[str, Any] | None,
    generate_kwargs: dict[str, Any] | None,
    extra_body: dict[str, Any] | None,
) -> dict[str, Any]:
    params = parameters or {}
    kwargs: dict[str, Any] = {}
    if not _omit(params.get("temperature")):
        kwargs["temperature"] = params["temperature"]
    if not _omit(params.get("top_p")):
        kwargs["top_p"] = params["top_p"]
    if not _omit(params.get("tools")):
        kwargs["tools"] = params["tools"]
    if not _omit(params.get("tool_choice")):
        kwargs["tool_choice"] = params["tool_choice"]
    if generate_kwargs:
        kwargs.update(generate_kwargs)
    if extra_body:
        kwargs["extra_body"] = {**extra_body, **kwargs.get("extra_body", {})}
    return kwargs


def _max_tokens(request: dict[str, Any]) -> int:
    current = request.get("max_tokens")
    parameters = request.get("parameters") or {}
    if _omit(current):
        current = parameters.get("max_tokens")
    if _omit(current):
        raise ValueError("Anthropic requires max_tokens; set it on the model card")
    return int(current)


async def call_api(payload: dict[str, Any]) -> Any:
    import importlib

    anthropic = importlib.import_module("anthropic")

    async def send(request: dict[str, Any]) -> Any:
        parameters = request.get("parameters") or {}
        client = anthropic.AsyncAnthropic(
            api_key=request["api_key"],
            base_url=request.get("base_url"),
            **(request.get("client_kwargs") or {}),
        )
        return await client.messages.create(
            model=request["model"],
            messages=format_messages(request.get("messages") or []),
            max_tokens=_max_tokens(request),
            stream=request.get("stream") is True,
            **_request_kwargs(
                parameters,
                request.get("generate_kwargs"),
                request.get("extra_body"),
            ),
        )

    return await _with_recovery(payload, send)
