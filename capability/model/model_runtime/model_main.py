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
    if isinstance(body, str):
        return [{"role": "user", "content": _prompt_text(body)}]
    if isinstance(body, list):
        return list(body)
    if isinstance(body, dict) and isinstance(body.get("messages"), list):
        return list(body["messages"])
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
    if kind != "prompt":
        raise ValueError(f"这个进程不能装入 {kind}")
    from capability.model.model_runtime import call_model as runtime

    result = await runtime.call_model(
        card_id,
        messages=_messages(body),
        **dict(call_params or {}),
    )
    return await _collect(runtime, card_id, result)


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


def _prompt_text(body: str) -> str:
    """A bare resource address is read from the file. The address itself stays the slip."""
    href = body.strip()
    if _resource_handle(href) is None:
        return body
    return _read_prompt_file(href)


def _resource_handle(value: str) -> str | None:
    from kernel.process.hypermedia.uri import parse_resource_uri

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
