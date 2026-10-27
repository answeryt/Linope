# -*- coding: utf-8 -*-
"""Assemble a JSON model card and dispatch to model_interface.call_api."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType
from typing import Any

MODEL_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_ROOT = MODEL_ROOT / "model_provider"
INTERFACE_ROOT = MODEL_ROOT / "model_API" / "model_interface"

UNSET = "UNSET"
PARAM_OVERRIDE_KEYS = (
    "max_tokens",
    "temperature",
    "top_p",
    "thinking_enable",
    "reasoning_effort",
    "parallel_tool_calls",
    "tools",
    "tool_choice",
    "voice",
)

_LEAF_CACHE: dict[str, ModuleType] = {}


def _is_unset(value: object) -> bool:
    return value is None or value == UNSET


def _load_leaf(path: Path | str) -> ModuleType:
    resolved = Path(path).resolve()
    cache_key = resolved.as_posix()
    cached = _LEAF_CACHE.get(cache_key)
    if cached is not None:
        return cached
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    spec = importlib.util.spec_from_file_location(
        f"linope_model_leaf_{resolved.stem}",
        resolved,
    )
    if spec is None or spec.loader is None:
        raise ImportError(resolved)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _LEAF_CACHE[cache_key] = module
    return module


def _card_path(card: str | Path) -> Path:
    raw = Path(card)
    if raw.is_file() and raw.suffix.lower() == ".json":
        return raw
    name = raw.stem if raw.suffix.lower() == ".json" else raw.name
    candidate = PROVIDER_ROOT / name / f"{name}.json"
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(
        f"model card JSON not found for {card!r}; expected {candidate}"
    )


def load_card(card: str | Path) -> dict[str, Any]:
    """Read one provider card from its JSON file."""
    loaded = json.loads(_card_path(card).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"model card must be a mapping: {card!r}")
    return loaded


def load_interface(card: str | Path | dict[str, Any]) -> ModuleType:
    cfg = card if isinstance(card, dict) else load_card(card)
    interface = cfg.get("interface")
    if _is_unset(interface) or interface == "":
        raise ValueError("model card is missing interface")
    return _load_leaf(INTERFACE_ROOT / f"{interface}.py")


def _clean_optional_str(value: object) -> str | None:
    if _is_unset(value) or value == "":
        return None
    return str(value)


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _env(name: object) -> str | None:
    if _is_unset(name) or name == "":
        return None
    value = os.environ.get(str(name))
    return value if value else None


def _resolve_api_key(card: dict[str, Any], api_key: object) -> str:
    if not _is_unset(api_key) and api_key != "":
        return str(api_key)
    env_name = card.get("api_key_env")
    if _is_unset(env_name) or env_name == "":
        raise ValueError("model card is missing api_key_env")
    from kernel.environment import current_room

    room = current_room()
    if room is not None:
        try:
            return room.identity.resolve_secret(str(env_name))
        except RuntimeError:
            raise RuntimeError(
                f"missing API key in environment variable {env_name}"
            ) from None
    value = os.environ.get(str(env_name))
    if not value:
        raise RuntimeError(f"missing API key in environment variable {env_name}")
    return value


def build_payload(
    card: dict[str, Any],
    *,
    messages: Any = None,
    context: Any = None,
    input_items: Any = None,
    contents: Any = None,
    api_key: str | None = None,
    organization: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Build the dict consumed by a model_interface.call_api."""
    parameters = _mapping(card.get("parameters"))
    extra_parameters = overrides.pop("parameters", None)
    if isinstance(extra_parameters, dict):
        parameters.update(extra_parameters)
    for key in PARAM_OVERRIDE_KEYS:
        if key in overrides:
            parameters[key] = overrides.pop(key)

    if messages is None:
        messages = card.get("messages")
    combined = [*_as_list(context), *_as_list(messages)]

    stream = overrides.pop("stream", card.get("stream"))
    model = overrides.pop("model", card.get("model"))
    base_url = overrides.pop("base_url", card.get("base_url"))
    interface = overrides.pop("interface", card.get("interface"))
    client_kwargs = _mapping(card.get("client_kwargs"))
    client_kwargs.update(_mapping(overrides.pop("client_kwargs", None)))
    generate_kwargs = _mapping(card.get("generate_kwargs"))
    generate_kwargs.update(_mapping(overrides.pop("generate_kwargs", None)))
    extra_body = _mapping(card.get("extra_body"))
    extra_body.update(_mapping(overrides.pop("extra_body", None)))

    if organization is None:
        organization = _env(card.get("organization_env"))

    payload: dict[str, Any] = {
        "interface": interface,
        "api_key": _resolve_api_key(card, api_key),
        "organization": organization,
        "base_url": _clean_optional_str(base_url),
        "model": model,
        "messages": combined,
        "stream": stream is True,
        "parameters": parameters,
        "client_kwargs": client_kwargs,
        "generate_kwargs": generate_kwargs,
        "extra_body": extra_body,
    }
    if input_items is not None:
        payload["input_items"] = input_items
    if contents is not None:
        payload["contents"] = contents
    max_tokens = parameters.get("max_tokens")
    if not _is_unset(max_tokens):
        payload["max_tokens"] = max_tokens
    payload.update(overrides)
    return payload


async def call_model(
    card: str | Path | dict[str, Any] = "openai_chat_model",
    *,
    messages: Any = None,
    context: Any = None,
    input_items: Any = None,
    contents: Any = None,
    api_key: str | None = None,
    organization: str | None = None,
    **overrides: Any,
) -> Any:
    """Load a JSON card, assemble a payload, and call the matching interface."""
    cfg = card if isinstance(card, dict) else load_card(card)
    payload = build_payload(
        cfg,
        messages=messages,
        context=context,
        input_items=input_items,
        contents=contents,
        api_key=api_key,
        organization=organization,
        **overrides,
    )
    leaf = load_interface(cfg)
    return await leaf.call_api(payload)


__all__ = [
    "INTERFACE_ROOT",
    "MODEL_ROOT",
    "PROVIDER_ROOT",
    "build_payload",
    "call_model",
    "load_card",
    "load_interface",
]
