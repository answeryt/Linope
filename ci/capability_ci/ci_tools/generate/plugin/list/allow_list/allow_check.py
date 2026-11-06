# -*- coding: utf-8 -*-
"""Allow list: the only handwritten inventory.

``paths`` are exempted from the generated deny list. Isolation edges in
``.gates/isolation-allowlist.json`` are pardoned after deny checks run.
Required injected parameters are listed under ``inject``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


PLUGIN_NAME = "plugin_allow"
PLUGIN_VERSION = "1.0"

PARDONABLE_ISOLATION_RULES = {
    "isolation.project_import",
    "isolation.sibling_import",
    "isolation.cross_plugin_import",
}


def run(context: dict[str, Any]) -> dict[str, Any]:
    _apply_allowlist(context)
    _check_injection(context)
    return context


def _apply_allowlist(context: dict[str, Any]) -> None:
    allowlist: list[tuple[str, str]] = list(context.get("allowlist") or [])
    if not allowlist:
        return
    kept: list[dict[str, Any]] = []
    for item in context.get("violations") or []:
        if item.get("rule") not in PARDONABLE_ISOLATION_RULES:
            kept.append(item)
            continue
        module_name = item.get("module")
        if isinstance(module_name, str) and _is_allowlisted(
            str(item.get("path", "")),
            module_name,
            allowlist,
        ):
            continue
        kept.append(item)
    context["violations"] = kept


def _is_allowlisted(
    rel: str,
    module_name: str,
    allowlist: list[tuple[str, str]],
) -> bool:
    rel_norm = rel.replace("\\", "/")
    for source, target in allowlist:
        source_norm = source.replace("\\", "/")
        if rel_norm != source_norm:
            continue
        if (
            target == module_name
            or module_name.startswith(target + ".")
            or target in module_name
            or target.replace("-", "_") in module_name
        ):
            return True
    return False


def _check_injection(context: dict[str, Any]) -> None:
    repo = Path(context["repo_root"])
    inject = _inject_map(context.get("allow_list") or {})
    if not inject:
        return
    for family in context["families"]:
        root = repo / family["root"]
        if not root.is_dir():
            continue
        for name in family.get("files") or []:
            path = root / name
            if not path.is_file() or path.name == "__init__.py":
                continue
            rel = path.relative_to(repo).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
            except (OSError, UnicodeError, SyntaxError):
                continue
            _check_injection_file(context, rel, tree, path.stem, inject)


def _inject_map(allow_list: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    raw = allow_list.get("inject")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, tuple[str, ...]] = {}
    for stem, names in raw.items():
        if isinstance(names, (list, tuple)):
            result[str(stem)] = tuple(str(name) for name in names)
    return result


def _check_injection_file(
    context: dict[str, Any],
    rel: str,
    tree: ast.Module,
    stem: str,
    inject: dict[str, tuple[str, ...]],
) -> None:
    required = inject.get(stem)
    if not required:
        return
    params = _all_param_names(tree)
    missing = [name for name in required if name not in params]
    if missing:
        context["violations"].append(
            _violation(
                "injection.estimator_param",
                rel,
                "caller must inject "
                + ", ".join(f"`{name}`" for name in missing)
                + " so this plugin does not import sibling estimators",
            )
        )


def _all_param_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            names.add(arg.arg)
        if node.args.vararg:
            names.add(node.args.vararg.arg)
        if node.args.kwarg:
            names.add(node.args.kwarg.arg)
    return names


def _violation(rule: str, path: str, detail: str) -> dict[str, str]:
    return {"rule": rule, "path": path, "detail": detail, "severity": "error"}
