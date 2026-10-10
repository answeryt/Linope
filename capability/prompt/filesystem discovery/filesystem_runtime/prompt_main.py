# -*- coding: utf-8 -*-
"""Command-line entry for assembling filesystem prompt leaves."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def _load_runtime() -> ModuleType:
    path = Path(__file__).with_name("filesystem_prompt_load.py")
    spec = importlib.util.spec_from_file_location("assemble_prompt_runtime_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble system and transient prompts. Sends only the user message.",
    )
    parser.add_argument("message", nargs="*", default=[], help="User message")
    parser.add_argument("--memory", default="", help="Transient memory context")
    parser.add_argument(
        "--plugin-context",
        default="",
        help="Transient plugin context",
    )
    parser.add_argument(
        "--gateway",
        default="",
        help="Transient gateway context",
    )
    return parser.parse_args(argv)


def _emit(assembled: dict[str, Any]) -> None:
    system = assembled.get("system") or ""
    user = assembled.get("user")
    if system:
        print(system)
        if user:
            print()
    if user not in (None, ""):
        print(user)


def load(kind, body, call_params=None):
    """Load prompt text through the existing assembler."""
    if kind != "prompt":
        raise ValueError(f"这个进程不能装入 {kind}")
    del call_params
    text = body if isinstance(body, str) else ""
    if isinstance(body, dict):
        text = str(body.get("user_content", ""))
    runtime = _load_runtime()
    return runtime.assemble_prompt(user_content=text)


def capability_profile(capability_id, changes):
    """Tell the process this prompt capability needs a prompt resource."""
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.PROMPT, identity={"id": capability_id}),
        ),
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    runtime = _load_runtime()
    assembled = runtime.assemble_prompt(
        user_content=" ".join(args.message),
        memory_context=args.memory,
        plugin_context=args.plugin_context,
        gateway_context=args.gateway,
    )
    _emit(assembled)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
