# -*- coding: utf-8 -*-
"""Host-sibling check: self-declared capability plugins and engine isolation."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Iterable


PLUGIN_NAME = "plugin_lip"
PLUGIN_VERSION = "1.0"

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    "pypyr-main",
    "faststream-main",
}
ENGINE_PREFIXES = ("kernel/compose/capability",)
ENGINE_MODULES = frozenset({"pluggy", "stevedore", "lip"})
DECLARATION_NAMES = frozenset({"CAPABILITY", "MODEL_CAPABILITY"})


def run(context: dict[str, Any]) -> dict[str, Any]:
    _check_self_declaration(context)
    _check_engine_imports(context)
    return context


def _check_self_declaration(context: dict[str, Any]) -> None:
    repo = Path(context["repo_root"])
    families = list(context.get("families") or [])
    families.extend(context.get("allowed_families") or [])
    for rel, path in _iter_family_files(repo, families):
        if not rel.endswith(".py"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, UnicodeError, SyntaxError) as exc:
            _error(context, "lip.capability.parse", rel, f"cannot parse plugin: {exc}")
            continue
        plugin_name = _const(tree, "PLUGIN_NAME")
        if plugin_name is None:
            continue
        if not _expects_declaration(rel):
            continue
        declaration = _declaration_name(tree)
        if declaration is None and not _has_capability_class(tree):
            _error(
                context,
                "lip.capability.declaration",
                rel,
                "plugin with PLUGIN_NAME must define a Capability subclass",
            )


def _check_engine_imports(context: dict[str, Any]) -> None:
    repo = Path(context["repo_root"])
    families = list(context.get("families") or [])
    families.extend(context.get("allowed_families") or [])
    for rel, path in _iter_family_files(repo, families):
        if _engine_path(rel):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, UnicodeError, SyntaxError):
            continue
        for module_name in _imported_modules(tree):
            engine = _engine_hit(module_name)
            if engine is None:
                continue
            _error(
                context,
                "lip.engine_import",
                rel,
                f"leaf plugins must not import `{engine}`; host loads resources by declaration",
            )


def _iter_family_files(repo: Path, families: Iterable[dict[str, Any]]) -> list[tuple[str, Path]]:
    seen: set[str] = set()
    result: list[tuple[str, Path]] = []
    for family in families:
        root = repo / family["root"]
        if not root.exists():
            continue
        named = family.get("files")
        if named:
            candidates = [root / name for name in named]
        else:
            candidates = sorted(root.rglob("*.py"))
        for path in candidates:
            if not path.is_file() or path.suffix != ".py":
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            rel = path.relative_to(repo).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            result.append((rel, path))
    return result


def _imported_modules(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names if alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def _engine_hit(module_name: str) -> str | None:
    for part in module_name.split("."):
        if part in ENGINE_MODULES:
            return part
    return None


def _engine_path(rel: str) -> bool:
    return any(rel == prefix or rel.startswith(prefix + "/") for prefix in ENGINE_PREFIXES)


def _expects_declaration(rel: str) -> bool:
    return rel.startswith("kernel/compose/") or rel.startswith("capability/model/")


def _const(tree: ast.AST, name: str) -> str | None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if (
            isinstance(target, ast.Name)
            and target.id == name
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            return value.value
    return None


def _declaration_name(tree: ast.AST) -> str | None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            target = node.target
        if isinstance(target, ast.Name) and target.id in DECLARATION_NAMES:
            return target.id
    return None


def _has_capability_class(tree: ast.AST) -> bool:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "Capability":
                return True
            if isinstance(base, ast.Attribute) and base.attr == "Capability":
                return True
    return False


def _error(context: dict[str, Any], rule: str, path: str, detail: str) -> None:
    context["violations"].append(
        {"rule": rule, "path": path, "detail": detail, "severity": "error"}
    )
