# -*- coding: utf-8 -*-
"""Deny list: plugin families must stay atomic and isolated.

Facade: no host.py, facade.py, or re-exporting __init__.py. Isolation: plugins
must not import other project plugins. Stdlib and unresolved third-party
imports are allowed here; explicit exceptions live in the allow-list plugin.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any, Iterable


PLUGIN_NAME = "plugin_deny"
PLUGIN_VERSION = "1.0"

FORBIDDEN_FILENAMES = {"host.py", "facade.py"}
SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    "pypyr-main",
}


def run(context: dict[str, Any]) -> dict[str, Any]:
    _check_facade(context)
    _check_isolation(context)
    return context


def _check_facade(context: dict[str, Any]) -> None:
    repo = Path(context["repo_root"])
    for family in context["families"]:
        root = repo / family["root"]
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            rel = path.relative_to(repo).as_posix()
            if path.name.lower() in FORBIDDEN_FILENAMES:
                context["violations"].append(
                    _violation(
                        "facade.filename",
                        rel,
                        "plugin family must not contain host.py or facade.py; "
                        "the application Host lives outside the family",
                    )
                )
            if path.name == "__init__.py":
                _check_init_barrel(context, rel, path)


def _check_init_barrel(context: dict[str, Any], rel: str, path: Path) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except (OSError, UnicodeError, SyntaxError):
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.level or 0) > 0:
            context["violations"].append(
                _violation(
                    "facade.barrel_init",
                    rel,
                    "__init__.py must not re-export sibling plugins; "
                    "Host imports each atomic file directly",
                )
            )
            return
        if isinstance(node, ast.ImportFrom) and node.module:
            context["violations"].append(
                _violation(
                    "facade.barrel_init",
                    rel,
                    "__init__.py must not import plugin modules",
                )
            )
            return


def _check_isolation(context: dict[str, Any]) -> None:
    repo = Path(context["repo_root"])
    families: list[dict[str, Any]] = context["families"]
    toplevel = tuple(context.get("project_toplevel") or ())
    stdlib = set(getattr(sys, "stdlib_module_names", ())) | {"__future__"}

    files = list(_iter_family_files(repo, families))
    context["file_count"] = len(files)
    family_by_file = _index_family_files(files)

    for rel, path, family in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, UnicodeError, SyntaxError) as exc:
            context["violations"].append(
                _violation(
                    "isolation.parse",
                    rel,
                    f"cannot parse plugin file: {exc}",
                )
            )
            continue
        for module_name in dict.fromkeys(_imported_modules(tree, rel)):
            if _is_stdlib(module_name, stdlib):
                continue
            if family["kind"] == "compression":
                context["violations"].append(
                    _isolation_violation(
                        "isolation.stdlib_only",
                        rel,
                        f"compression plugin may import stdlib only, not `{module_name}`",
                        module_name,
                    )
                )
                continue
            target = _resolve_module_file(repo, module_name)
            if target is None:
                if module_name.split(".", 1)[0] in toplevel:
                    context["violations"].append(
                        _isolation_violation(
                            "isolation.project_import",
                            rel,
                            f"imports project module `{module_name}`",
                            module_name,
                        )
                    )
                continue
            target_rel = target.relative_to(repo).as_posix()
            if target_rel == rel:
                continue
            if target_rel not in family_by_file and not _is_project_path(
                target_rel, toplevel
            ):
                continue
            source_family = family["id"]
            target_family = family_by_file.get(target_rel)
            if target_family == source_family:
                context["violations"].append(
                    _isolation_violation(
                        "isolation.sibling_import",
                        rel,
                        f"imports sibling plugin `{target_rel}` "
                        f"(family `{source_family}`)",
                        module_name,
                    )
                )
            else:
                context["violations"].append(
                    _isolation_violation(
                        "isolation.cross_plugin_import",
                        rel,
                        f"imports `{target_rel}` "
                        f"(family `{target_family or 'project'}`)",
                        module_name,
                    )
                )


def _violation(rule: str, path: str, detail: str) -> dict[str, str]:
    return {"rule": rule, "path": path, "detail": detail, "severity": "error"}


def _isolation_violation(
    rule: str,
    path: str,
    detail: str,
    module_name: str,
) -> dict[str, str]:
    item = _violation(rule, path, detail)
    item["module"] = module_name
    return item


def _iter_family_files(
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
        named = family.get("files")
        glob = family.get("glob")
        if named:
            candidates.extend(root / name for name in named)
        elif glob:
            candidates.extend(sorted(root.glob(glob)))
        else:
            candidates.extend(sorted(root.rglob("*.py")))
        for path in candidates:
            if not path.is_file() or path.suffix != ".py":
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            rel = path.relative_to(repo).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            result.append((rel, path, family))
    return result


def _index_family_files(
    files: list[tuple[str, Path, dict[str, Any]]],
) -> dict[str, str]:
    return {rel: family["id"] for rel, _path, family in files}


def _imported_modules(tree: ast.AST, rel: str) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            absolute = _resolve_from_import(rel, node)
            if absolute:
                names.append(absolute)
            if node.module is None and node.level:
                for alias in node.names:
                    child = _resolve_from_import(
                        rel,
                        ast.ImportFrom(
                            module=alias.name,
                            names=[ast.alias(name="*", asname=None)],
                            level=node.level,
                        ),
                    )
                    if child:
                        names.append(child)
    return names


def _resolve_from_import(rel: str, node: ast.ImportFrom) -> str | None:
    parts = Path(rel).with_suffix("").parts
    package = parts[:-1]
    level = node.level or 0
    if level:
        if level - 1 > len(package):
            return None
        anchor = package[: len(package) - (level - 1)]
        if node.module:
            return ".".join((*anchor, *node.module.split(".")))
        return ".".join(anchor) if anchor else None
    return node.module


def _is_stdlib(module_name: str, stdlib: set[str]) -> bool:
    head = module_name.split(".", 1)[0]
    return head in stdlib or module_name in stdlib


def _is_project_path(rel: str, toplevel: tuple[str, ...]) -> bool:
    head = rel.split("/", 1)[0]
    return head in toplevel


def _resolve_module_file(repo: Path, module_name: str) -> Path | None:
    relative = Path(*module_name.split("."))
    py_file = repo / relative.with_suffix(".py")
    if py_file.is_file():
        return py_file
    package = repo / relative / "__init__.py"
    if package.is_file():
        return package
    return None
