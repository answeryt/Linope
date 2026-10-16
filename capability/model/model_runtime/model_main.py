# -*- coding: utf-8 -*-
"""Command-line entry for calling a model from a JSON card."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_runtime() -> ModuleType:
    path = Path(__file__).with_name("call_model.py")
    spec = importlib.util.spec_from_file_location("call_model_runtime_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _messages(body: Any) -> list[Any]:
    messages, _extras = _message_request(body)
    return messages


def _message_request(body: Any) -> tuple[list[Any], dict[str, Any]]:
    """A string stays one user message. A mapping may also carry tool declarations."""
    if isinstance(body, str):
        return [{"role": "user", "content": _prompt_text(body)}], {}
    if isinstance(body, list):
        return list(body), {}
    if isinstance(body, dict) and isinstance(body.get("messages"), list):
        extras: dict[str, Any] = {}
        if body.get("tools") not in (None, [], "UNSET"):
            extras["tools"] = body["tools"]
        if body.get("tool_choice") not in (None, "", "UNSET"):
            extras["tool_choice"] = body["tool_choice"]
        return list(body["messages"]), extras
    raise TypeError("prompt 的内容必须是文本或消息")


async def _collect(runtime: ModuleType, card_id: str, result: Any) -> Any:
    leaf = runtime.load_interface(card_id)
    if hasattr(result, "__aiter__"):
        assembler = None
        if hasattr(leaf, "parse_stream_parts"):
            from capability.model.model_runtime.assembler import BlockAssembler

            assembler = BlockAssembler()
        parts: list[str] = []
        async for chunk in result:
            if assembler is not None:
                for part in leaf.parse_stream_parts(chunk):
                    assembler.push(part)
                    _forward_display(part)
            else:
                piece = leaf.parse_stream_chunk(chunk)
                if piece:
                    parts.append(piece)
        if assembler is not None:
            return assembler.finish().to_payload()
        return "".join(parts)
    if hasattr(leaf, "parse_response_turn"):
        turn = leaf.parse_response_turn(result)
        if turn is not None:
            return turn
    text = leaf.parse_response(result)
    return text if text is not None else result


def _forward_display(part: Any) -> None:
    """Hand one text fragment to the terminal without waiting for the final turn."""
    if not isinstance(part, dict) or part.get("type") not in {"text", "text-delta"}:
        return
    text = part.get("text")
    if not text:
        return
    from kernel.command.live_stream import publish_text

    publish_text(str(text))


def _turn_text(result: Any) -> str | None:
    if not isinstance(result, dict) or result.get("type") != "model_turn":
        return None
    pieces: list[str] = []
    for block in result.get("blocks") or ():
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if text:
                pieces.append(str(text))
    return "\n".join(pieces)


async def _emit(leaf: ModuleType, result: Any) -> None:
    if hasattr(result, "__aiter__"):
        parts: list[str] = []
        async for chunk in result:
            piece = leaf.parse_stream_chunk(chunk)
            if piece:
                parts.append(piece)
        print("".join(parts))
        return
    turn_text = _turn_text(result)
    if turn_text is not None:
        print(turn_text)
        return
    text = leaf.parse_response(result)
    print(text if text is not None else result)


def load_named_card(
    card_id: str,
    kind: str,
    body: Any,
    call_params: dict[str, Any] | None = None,
) -> Any:
    """Synchronous compatibility wrapper for :func:`load_named_card_async`."""
    return asyncio.run(load_named_card_async(card_id, kind, body, call_params))


async def load_named_card_async(
    card_id: str,
    kind: str,
    body: Any,
    call_params: dict[str, Any] | None = None,
) -> Any:
    """Load a prompt without creating a nested event loop per request."""
    if kind != "message":
        raise ValueError(f"这个进程不能装入 {kind}")
    from capability.model.model_runtime import call_model as runtime

    messages, extras = _message_request(body)
    result = await runtime.call_model(
        card_id,
        messages=messages,
        **{**dict(call_params or {}), **extras},
    )
    collected = await _collect(runtime, card_id, result)
    _remember_context(card_id, call_params, messages, collected)
    return collected


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call a model from a JSON card. Sends only the user message.",
    )
    parser.add_argument("message", nargs="+", help="User message")
    parser.add_argument(
        "--card",
        default="openai_chat_model",
        help="Provider card id or path to a JSON file",
    )
    return parser.parse_args(argv)


async def _async_main(args: argparse.Namespace, runtime: ModuleType) -> int:
    result = await runtime.call_model(
        args.card,
        messages=[{"role": "user", "content": " ".join(args.message)}],
    )
    await _emit(runtime.load_interface(args.card), result)
    return 0


def _remember_context(
    card_id: str,
    call_params: dict[str, Any] | None,
    messages: list[Any],
    result: Any,
) -> None:
    """Write this call's window occupancy onto the bound process, if there is one."""
    from kernel.resource.account.bind import current_store
    from kernel.resource.account.recorded import record_context

    store = current_store()
    if store is None or not isinstance(result, dict) or result.get("type") != "model_turn":
        return
    from capability.model.model_API.model_paramaters.context_limits.context_limits import (
        resolve_default_context_length,
    )
    from capability.model.model_API.model_paramaters.tokens.tokens import (
        estimate_text_tokens_rough,
    )
    from capability.model.model_runtime.call_model import load_card
    from kernel.environment import current_room

    room = current_room()
    process_id = str(getattr(getattr(room, "shell", None), "process_id", "") or "")
    if not process_id:
        return
    try:
        usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
        output_text = _turn_text(result) or ""
        if "output" in usage:
            output_tokens = int(usage["output"])
        else:
            output_tokens = estimate_text_tokens_rough(output_text)
        if "input" in usage:
            input_tokens = int(usage["input"])
        else:
            input_tokens = estimate_text_tokens_rough(_input_text(messages))
        card = load_card(card_id)
        model = str((call_params or {}).get("model") or card.get("model") or "")
        record_context(
            store,
            process_id,
            occupied=input_tokens + output_tokens,
            ceiling=resolve_default_context_length(model),
            output_tokens=output_tokens,
        )
    except Exception:
        # The reply is already formed. A ledger problem must not discard it.
        return


def _input_text(messages: list[Any]) -> str:
    parts: list[str] = []
    for message in messages or []:
        if isinstance(message, str):
            parts.append(message)
            continue
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif content is not None:
            parts.append(str(content))
    return "\n".join(parts)


def _prompt_text(body: str) -> str:
    """A bare resource address is read from the file. The address itself stays the slip."""
    href = body.strip()
    if _resource_handle(href) is None:
        return body
    return _read_prompt_file(href)


def _resource_handle(value: str) -> str | None:
    from kernel.hypermedia.uri import parse_resource_uri

    try:
        return parse_resource_uri(value)
    except ValueError:
        return None


def _read_prompt_file(href: str) -> str:
    from kernel.environment import current_room
    from kernel.environment.file_io import door_for
    from kernel.process.ledger import FileResourceStore
    from kernel.resource.store.locator import default_store_locator, local_path

    handle = _resource_handle(href)
    if handle is None:
        raise ValueError("没有这条链接")
    locator = default_store_locator()
    if not str(locator).startswith(("file:", "local:")):
        raise ValueError("提示词地址只从本地账本读取")
    store = FileResourceStore(local_path(locator), reap=False)
    try:
        found = store.link_at(handle)
    finally:
        store.close()
    if found is None:
        raise ValueError("没有这条链接")
    page, _link = found
    return door_for(current_room(), None).read_text(str(page.address))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    runtime = _load_runtime()
    return asyncio.run(_async_main(args, runtime))


if __name__ == "__main__":
    raise SystemExit(main())
