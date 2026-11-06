# -*- coding: utf-8 -*-
"""Host-sibling check: each plugin family must expose the documented entry point.

Contracts are inferred from files on disk, not from a Host kind table:
- ``*_plugin.py`` -> PLUGIN_NAME, PLUGIN_VERSION
- ``*_check.py`` / ``*_generate.py`` -> PLUGIN_NAME, PLUGIN_VERSION, run(context)
- a family that already has ``call_api`` -> every module exposes ``call_api``
- a family that already has ``apply_*`` -> every module exposes ``apply_<stem>``
- otherwise at least one public function or class

Cluster kind consistency for ``CAPABILITY`` / ``MODEL_CAPABILITY`` lives in
``descriptor_check.py``. This file does not special-case ``model.fallback``.
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
    grouped = _group_python(repo, context["families"])
    for files in grouped:
        contract = _infer_contract(files)
        for rel, path, tree in files:
            _check_file(context, rel, path, tree, contract, mcp_names)
    _require_unique(context, mcp_names, "surface.unique_plugin_name")
    return context


def _check_file(
    context: dict[str, Any],
    rel: str,
    path: Path,
    tree: ast.AST,
    contract: str,
    mcp_names: list[str],
) -> None:
    if path.name == "plugin_generate.py":
        _require_function(context, rel, tree, "main")
        return
    if path.name.endswith("_check.py") or path.name.endswith("_generate.py"):
        _require_constants(context, rel, tree, ("PLUGIN_NAME", "PLUGIN_VERSION"))
        _require_function(context, rel, tree, "run")
        return
    if path.name.endswith("_plugin.py"):
        _require_constants(context, rel, tree, ("PLUGIN_NAME", "PLUGIN_VERSION"))
        name = _constant_str(tree, "PLUGIN_NAME")
        if name:
            mcp_names.append(name)
        return
    if contract == "interface":
        _require_function(context, rel, tree, "call_api")
        return
    if contract == "apply_param":
        if not any(name.startswith("apply_") for name in _public_functions(tree)):
            context["violations"].append(
                _violation(
                    "surface.entry_point",
                    rel,
                    "apply_param family requires an apply_* function",
                )
            )
        return
    if not _public_functions(tree) and not _public_classes(tree):
        context["violations"].append(
            _violation(
                "surface.public_api",
                rel,
                "plugin must expose a public function or class",
            )
        )


def _infer_contract(
    files: list[tuple[str, Path, ast.AST]],
) -> str:
    has_call_api = False
    has_apply = False
    for _rel, path, tree in files:
        if path.name in SKIP_NAMES:
            continue
        names = _public_functions(tree)
        if "call_api" in names:
            has_call_api = True
        if any(name.startswith("apply_") for name in names):
            has_apply = True
    if has_call_api:
        return "interface"
    if has_apply:
        return "apply_param"
    return "public_api"


def _group_python(
    repo: Path,
    families: Iterable[dict[str, Any]],
) -> list[list[tuple[str, Path, ast.AST]]]:
    grouped: list[list[tuple[str, Path, ast.AST]]] = []
    current_id: object | None = None
    bucket: list[tuple[str, Path, ast.AST]] = []
    for rel, path, family in _iter_python(repo, families):
        if path.name in SKIP_NAMES:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, UnicodeError, SyntaxError):
            continue
        family_id = family.get("root") or family.get("id")
        if bucket and family_id != current_id:
            grouped.append(bucket)
            bucket = []
        current_id = family_id
        bucket.append((rel, path, tree))
    if bucket:
        grouped.append(bucket)
    return grouped


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


def _violation(rule: str, path: str, detail: str) -> dict[str, str]:
    return {"rule": rule, "path": path, "detail": detail, "severity": "error"}
