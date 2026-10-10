# -*- coding: utf-8 -*-
"""Filesystem discovery of system and transient prompt leaves."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

DISCOVERY_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_BUILDER_LEAF = DISCOVERY_ROOT / "system_prompt" / "system_prompt_builder.py"
SYSTEM_LOAD_LEAF = DISCOVERY_ROOT / "system_prompt" / "system_prompt_load.py"
TRANSIENT_BUILDER_LEAF = (
    DISCOVERY_ROOT / "transient_prompt" / "transient_prompt_builder.py"
)

_LEAF_CACHE: dict[str, ModuleType] = {}

SystemBuilder = Callable[..., str]
TransientBuilder = Callable[..., str | None]


def _load_leaf(path: Path | str) -> ModuleType:
    resolved = Path(path).resolve()
    cache_key = resolved.as_posix()
    cached = _LEAF_CACHE.get(cache_key)
    if cached is not None:
        return cached
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    spec = importlib.util.spec_from_file_location(
        f"linope_prompt_leaf_{resolved.stem}",
        resolved,
    )
    if spec is None or spec.loader is None:
        raise ImportError(resolved)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _LEAF_CACHE[cache_key] = module
    return module


def _default_system_text(
    context: Mapping[str, Any] | None,
    system_plugin: Any,
) -> str:
    builder = _load_leaf(SYSTEM_BUILDER_LEAF)
    plugin = system_plugin
    if plugin is None:
        plugin = _load_leaf(SYSTEM_LOAD_LEAF).SYSTEM_PROMPT_PLUGIN
    return builder.build_system_prompt(context, plugin=plugin)


def _default_transient(
    content: Any,
    *,
    memory_context: str,
    plugin_context: str,
    gateway_context: str,
    memory_formatter: Any,
    context: Mapping[str, Any] | None,
) -> tuple[str, Any]:
    leaf = _load_leaf(TRANSIENT_BUILDER_LEAF)
    suffix = leaf.TRANSIENT_PROMPT_BUILDER_PLUGIN.build_context(
        memory_context=memory_context,
        plugin_context=plugin_context,
        gateway_context=gateway_context,
        memory_formatter=memory_formatter,
        context=context,
    )
    composed = leaf.build_transient_prompt(
        content,
        memory_context=memory_context,
        plugin_context=plugin_context,
        gateway_context=gateway_context,
        memory_formatter=memory_formatter,
        context=context,
    )
    return suffix, composed


def assemble_prompt(
    context: Mapping[str, Any] | None = None,
    *,
    user_content: Any = "",
    memory_context: str = "",
    plugin_context: str = "",
    gateway_context: str = "",
    memory_formatter: Any = None,
    system_builder: SystemBuilder | None = None,
    transient_builder: TransientBuilder | None = None,
    system_plugin: Any = None,
) -> dict[str, Any]:
    """Join injected or file-loaded builders into one prompt envelope.

    Discovery of Markdown cards stays inside the load leaves. This runtime only
    loads builder/load modules by path and calls their public functions.
    """

    if system_builder is None:
        system = _default_system_text(context, system_plugin)
    else:
        system = system_builder(context)

    if not isinstance(system, str):
        raise TypeError("system builder must return a string")

    if transient_builder is None:
        suffix, composed = _default_transient(
            user_content,
            memory_context=memory_context,
            plugin_context=plugin_context,
            gateway_context=gateway_context,
            memory_formatter=memory_formatter,
            context=context,
        )
        user = composed if composed is not None else user_content
    else:
        composed = transient_builder(
            user_content,
            memory_context=memory_context,
            plugin_context=plugin_context,
            gateway_context=gateway_context,
            memory_formatter=memory_formatter,
            context=context,
        )
        suffix = composed if isinstance(composed, str) else ""
        user = composed if composed is not None else user_content

    if not isinstance(suffix, str):
        raise TypeError("transient suffix must be a string")

    return {
        "system": system,
        "transient": suffix,
        "user": user,
    }


__all__ = [
    "DISCOVERY_ROOT",
    "SYSTEM_BUILDER_LEAF",
    "SYSTEM_LOAD_LEAF",
    "TRANSIENT_BUILDER_LEAF",
    "assemble_prompt",
]
