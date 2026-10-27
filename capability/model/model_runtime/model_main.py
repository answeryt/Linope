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
    raise TypeError("prompt content must be text or messages")


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
    from kernel.command.screen.live_stream import publish_text

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
        raise ValueError(f"This process cannot load {kind}")
    from capability.model.model_runtime import call_model as runtime

    messages, extras = _message_request(body)
    forwarded = dict(call_params or {})
    forwarded.pop("permission", None)
    forwarded.pop("capabilities", None)
    result = await runtime.call_model(
        card_id,
        messages=messages,
        **{**forwarded, **extras},
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
    from kernel.hypermedia.uri import parse_resource_uri

    try:
        return parse_resource_uri(value)
    except ValueError:
        return None


def _read_prompt_file(href: str) -> str:
    from kernel.environment import current_room
    from kernel.environment.file_io import door_for

    handle = _resource_handle(href)
    if handle is None:
        raise ValueError("No such link")
    locator = _store_locator()
    if not locator.startswith(("file:", "local:")):
        raise ValueError("Prompt addresses are read only from the local ledger")
    address = _linked_address(_store_path(locator), handle)
    if address is None:
        raise ValueError("No such link")
    return door_for(current_room(), None).read_text(address)


def _store_locator() -> str:
    """The project resource ledger. An environment value wins over the saved path."""
    import os

    raw = os.environ.get("LINOPE_RESOURCE_STORE", "").strip()
    if not raw:
        raw = str(_project_config().get("resource_store") or "").strip()
    if not raw:
        raw = "file:.linope/resources.json"
    return _normalize_locator(raw)


def _normalize_locator(value: str) -> str:
    import re

    if re.match(r"^[A-Za-z][A-Za-z0-9+._-]*:", value) is not None and not (
        len(value) >= 2 and value[1] == ":"
    ):
        return value
    return f"file:{value}"


def _project_config() -> dict[str, Any]:
    import json

    from kernel.process.process_creat.instances import repo_root

    path = repo_root() / ".linope" / "config.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _store_path(locator: str) -> Path:
    from kernel.process.process_creat.instances import repo_root

    raw = locator.split(":", 1)[1]
    if raw.startswith("//"):
        raw = raw[2:]
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = repo_root() / path
    return path


def _linked_address(path: Path, handle: str) -> str | None:
    """The file address saved beside this handle. Missing ledgers have no link."""
    import json

    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Cannot read local storage {path}: {exc}") from exc
    pages = {}
    if isinstance(payload, dict):
        sections = payload.get("sections")
        resource = sections.get("resource") if isinstance(sections, dict) else None
        found = resource.get("pages") if isinstance(resource, dict) else None
        if isinstance(found, dict):
            pages = found
    for item in pages.values():
        if not isinstance(item, dict):
            continue
        link = item.get("link")
        page = item.get("page")
        if not isinstance(link, dict) or not isinstance(page, dict):
            continue
        if str(link.get("handle") or "") != handle:
            continue
        address = page.get("address")
        if address:
            return str(address)
    return None


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    runtime = _load_runtime()
    return asyncio.run(_async_main(args, runtime))


if __name__ == "__main__":
    raise SystemExit(main())
