# -*- coding: utf-8 -*-
"""Surface check: each plugin family must expose the documented entry point.

Contracts come from this repo's plugin READMEs:
- apply_param -> apply_<filename>
- interface -> call_api
- mcp *_plugin.py -> PLUGIN_NAME, PLUGIN_VERSION
- compression/token/fallback -> at least one public function
- ci *_check.py -> PLUGIN_NAME, PLUGIN_VERSION, run(context)
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Iterable


PLUGIN_NAME = "plugin_surface"
PLUGIN_VERSION = "1.0"

SKIP_NAMES = {"__init__.py"}


def run(context: dict[str, Any]) -> dict[str, Any]:
    repo = Path(context["repo_root"])
    mcp_names: list[str] = []
    for rel, path, family in _iter_python(repo, context["families"]):
        if path.name in SKIP_NAMES:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, UnicodeError, SyntaxError):
            continue
        kind = family["kind"]
        if kind == "apply_param":
            _require_function(context, rel, tree, f"apply_{path.stem}")
        elif kind == "interface":
            _require_function(context, rel, tree, "call_api")
        elif kind == "mcp":
            _require_constants(context, rel, tree, ("PLUGIN_NAME", "PLUGIN_VERSION"))
            name = _constant_str(tree, "PLUGIN_NAME")
            if name:
                mcp_names.append(name)
        elif kind in {"compression", "token", "fallback", "mcp_transport", "mcp_session"}:
            if not _public_functions(tree) and not _public_classes(tree):
                context["violations"].append(
                    _violation(
                        "surface.public_api",
                        rel,
                        "plugin must expose a public function or class",
                    )
                )
        elif kind == "prompt":
            if not _public_classes(tree) and not _has_name_suffix(tree, "Plugin"):
                if not _public_functions(tree):
                    context["violations"].append(
                        _violation(
                            "surface.plugin_type",
                            rel,
                            "prompt plugin must expose a Plugin type or public function",
                        )
                    )
        elif kind == "message":
            if not _public_classes(tree):
                context["violations"].append(
                    _violation(
                        "surface.message_model",
                        rel,
                        "message plugin must expose a public model class",
                    )
                )
        elif kind == "ci":
            if path.name.endswith("_check.py"):
                _require_constants(context, rel, tree, ("PLUGIN_NAME", "PLUGIN_VERSION"))
                _require_function(context, rel, tree, "run")
            elif path.name == "plugin_generate.py":
                _require_function(context, rel, tree, "main")
    _require_unique(context, mcp_names, "surface.unique_plugin_name")
    return context


def _iter_python(
    repo: Path,
    families: Iterable[dict[str, Any]],
) -> list[tuple[str, Path, dict[str, Any]]]:
    seen: set[str] = set()
    result: list[tuple[str, Path, dict[str, Any]]] = []
    for family in families:
        root = repo / family["root"]
        if not root.exists():
            continue
        candidates: list[Path] = []
        if family.get("files"):
            candidates.extend(root / name for name in family["files"])
        elif family.get("glob"):
            candidates.extend(sorted(root.glob(family["glob"])))
        else:
            candidates.extend(sorted(root.rglob("*.py")))
        for path in candidates:
            if not path.is_file() or path.suffix != ".py":
                continue
            rel = path.relative_to(repo).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            result.append((rel, path, family))
    return result


def _require_function(
    context: dict[str, Any],
    rel: str,
    tree: ast.AST,
    name: str,
) -> None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return
    context["violations"].append(
        _violation("surface.entry_point", rel, f"missing required function `{name}`")
    )


def _require_constants(
    context: dict[str, Any],
    rel: str,
    tree: ast.AST,
    names: tuple[str, ...],
) -> None:
    assigned = _assigned_names(tree)
    for name in names:
        if name not in assigned:
            context["violations"].append(
                _violation(
                    "surface.identity",
                    rel,
                    f"missing required constant `{name}`",
                )
            )


def _require_unique(
    context: dict[str, Any],
    names: list[str],
    rule: str,
) -> None:
    seen: dict[str, int] = {}
    for name in names:
        seen[name] = seen.get(name, 0) + 1
    for name, count in seen.items():
        if count > 1:
            context["violations"].append(
                _violation(rule, "tools/external_tools/mcp", f"duplicate PLUGIN_NAME `{name}`")
            )


def _assigned_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _constant_str(tree: ast.AST, name: str) -> str | None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        return node.value.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


def _public_functions(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            names.append(node.name)
    return names


def _public_classes(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            names.append(node.name)
    return names


def _has_name_suffix(tree: ast.AST, suffix: str) -> bool:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.ClassDef) and node.name.endswith(suffix):
            return True
    return False


def _violation(rule: str, path: str, detail: str) -> dict[str, str]:
    return {"rule": rule, "path": path, "detail": detail, "severity": "error"}
