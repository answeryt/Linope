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


def _gemini_role(role: object) -> str:
    if role == "assistant":
        return "model"
    if role == "model":
        return "model"
    return "user"


def _parts(content: Any) -> list[Any]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{"text": content}]
    if not isinstance(content, list):
        content = [content]
    parts: list[Any] = []
    for part in content:
        if isinstance(part, str):
            parts.append({"text": part})
            continue
        if isinstance(part, dict):
            if "text" in part or "inline_data" in part or "file_data" in part:
                parts.append(part)
                continue
            if part.get("type") == "text":
                parts.append({"text": part.get("text", "")})
                continue
        kind = getattr(part, "type", None)
        if kind == "text":
            parts.append({"text": getattr(part, "text", "")})
        elif kind == "thinking":
            parts.append({"text": getattr(part, "thinking", "")})
        elif kind == "hint":
            hint = getattr(part, "hint", "")
            text = " ".join(str(item) for item in hint) if isinstance(hint, list) else str(hint)
            parts.append({"text": text})
        elif kind == "data":
            source = getattr(part, "source", None)
            media_type = getattr(source, "media_type", "application/octet-stream")
            if getattr(source, "type", None) == "url":
                parts.append({"file_data": {"file_uri": getattr(source, "url", "")}})
            else:
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": media_type,
                            "data": getattr(source, "data", ""),
                        }
                    }
                )
        else:
            parts.append(part)
    return parts


def format_messages(messages: Any) -> list[dict[str, Any]]:
    if messages is None:
        return []
    if isinstance(messages, str):
        return [{"role": "user", "parts": [{"text": messages}]}]
    if isinstance(messages, dict):
        messages = [messages]
    result: list[dict[str, Any]] = []
    pending: list[Any] = []

    def flush() -> None:
        if not pending:
            return
        result.append({"role": "user", "parts": _parts(pending)})
        pending.clear()

    for item in messages:
        if isinstance(item, dict) and ("role" in item or "parts" in item):
            flush()
            if "parts" in item:
                result.append(
                    {
                        "role": _gemini_role(item.get("role", "user")),
                        "parts": item.get("parts") or [],
                    }
                )
                continue
            result.append(
                {
                    "role": _gemini_role(item.get("role", "user")),
                    "parts": _parts(item.get("content")),
                }
            )
            continue
        pending.append(item)
    flush()
    return result


def parse_response(result: Any) -> str | None:
    text = getattr(result, "text", None)
    if isinstance(text, str) and text:
        return text
    return None


def parse_stream_chunk(chunk: Any) -> str:
    text = getattr(chunk, "text", None)
    return str(text) if isinstance(text, str) and text else ""


def _config(
    parameters: dict[str, Any] | None,
    generate_kwargs: dict[str, Any] | None,
    extra_body: dict[str, Any] | None,
) -> dict[str, Any]:
    params = parameters or {}
    config: dict[str, Any] = {}
    if not _omit(params.get("temperature")):
        config["temperature"] = params["temperature"]
    if not _omit(params.get("top_p")):
        config["top_p"] = params["top_p"]
    if not _omit(params.get("max_tokens")):
        config["max_output_tokens"] = params["max_tokens"]
    if not _omit(params.get("tools")):
        config["tools"] = params["tools"]
    if not _omit(params.get("tool_choice")):
        config["tool_choice"] = params["tool_choice"]
    if generate_kwargs:
        config.update(generate_kwargs)
    if extra_body:
        config["extra_body"] = {**extra_body, **config.get("extra_body", {})}
    return config


async def call_api(payload: dict[str, Any]) -> Any:
    import importlib

    genai = importlib.import_module("google.genai")

    async def send(request: dict[str, Any]) -> Any:
        client = genai.Client(
            api_key=request["api_key"],
            **(request.get("client_kwargs") or {}),
        )
        config = _config(
            request.get("parameters"),
            request.get("generate_kwargs"),
            request.get("extra_body"),
        )
        raw = request.get("contents")
        contents = format_messages(raw if raw is not None else request.get("messages") or [])
        if request.get("stream") is True:
            return await client.aio.models.generate_content_stream(
                model=request["model"],
                contents=contents,
                config=config,
            )
        return await client.aio.models.generate_content(
            model=request["model"],
            contents=contents,
            config=config,
        )

    return await _with_recovery(payload, send)
