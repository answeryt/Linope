# -*- coding: utf-8 -*-
"""SDK-boundary check: model_interface stays a thin, lazy SDK wrapper.

model_interface README: one file per Provider API, only call_api, no message
formatting / retry / tool conversion. SDK clients are imported inside
call_api, not at module top level.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


PLUGIN_NAME = "plugin_sdk_boundary"
PLUGIN_VERSION = "1.0"

SDK_ROOTS = {"openai", "anthropic", "google", "genai"}
FORBIDDEN_NAME_HINTS = {
    "retry",
    "format_message",
    "format_messages",
    "parse_response",
    "convert_tools",
    "tool_choice_convert",
}


def run(context: dict[str, Any]) -> dict[str, Any]:
    repo = Path(context["repo_root"])
    for family in context["families"]:
        if family["kind"] != "interface":
            continue
        root = repo / family["root"]
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.py")):
            if path.name == "__init__.py":
                continue
            rel = path.relative_to(repo).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
            except (OSError, UnicodeError, SyntaxError):
                continue
            _check_module_level_sdk(context, rel, tree)
            _check_forbidden_helpers(context, rel, tree)
    return context


def _check_module_level_sdk(
    context: dict[str, Any],
    rel: str,
    tree: ast.Module,
) -> None:
    for node in tree.body:
        imported = _import_roots(node)
        overlap = imported & SDK_ROOTS
        if overlap:
            context["violations"].append(
                _violation(
                    "sdk.lazy_import",
                    rel,
                    "Provider SDK must be imported inside call_api, not at "
                    f"module top level ({', '.join(sorted(overlap))})",
                )
            )


def _check_forbidden_helpers(
    context: dict[str, Any],
    rel: str,
    tree: ast.Module,
) -> None:
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == "call_api":
            continue
        if node.name.startswith("_"):
            continue
        if node.name in FORBIDDEN_NAME_HINTS or any(
            hint in node.name for hint in FORBIDDEN_NAME_HINTS
        ):
            context["violations"].append(
                _violation(
                    "sdk.thin_wrapper",
                    rel,
                    f"public helper `{node.name}` belongs outside model_interface "
                    "(no retry, formatting, or tool conversion here)",
                )
            )


def _import_roots(node: ast.AST) -> set[str]:
    roots: set[str] = set()
    if isinstance(node, ast.Import):
        for alias in node.names:
            roots.add(alias.name.split(".", 1)[0])
    elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
        roots.add(node.module.split(".", 1)[0])
    return roots


def _violation(rule: str, path: str, detail: str) -> dict[str, str]:
    return {"rule": rule, "path": path, "detail": detail, "severity": "error"}
