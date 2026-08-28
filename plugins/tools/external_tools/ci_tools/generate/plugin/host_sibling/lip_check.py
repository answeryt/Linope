# -*- coding: utf-8 -*-
"""Host-sibling check: named socket declarations and engine isolation.

Socket inventory comes from the Host composition. Leaf plugins must not import
pluggy, stevedore, or lip; Host looks up plugs by name and injects them.
This check validates source declarations only; runtime callable contracts stay
in stevedore.lip. Socket identities must be static strings so CI never imports
leaf plugins. Cross-plugin file imports stay in deny_check.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import Any, Iterable


PLUGIN_NAME = "plugin_lip"
PLUGIN_VERSION = "1.0"
COMPOSITION_PATH = "kernel/thred/plugin/composition.yaml"

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    "pypyr-main",
    "faststream-main",
}
ENGINE_PREFIXES = (
    "kernel/thred/plugin/host",
    "kernel/thred/plugin/manager",
    "kernel/thred/plugin/recipes",
    "kernel/thred/plugin/signals",
    "kernel/thred/plugin/tests",
)
ENGINE_MODULES = frozenset({"pluggy", "stevedore", "lip"})


def run(context: dict[str, Any]) -> dict[str, Any]:
    _check_sockets(context)
    _check_engine_imports(context)
    return context


def _check_sockets(context: dict[str, Any]) -> None:
    repo = Path(context["repo_root"])
    composition_path = repo / COMPOSITION_PATH
    try:
        yaml = importlib.import_module("yaml")
    except ImportError:
        _error(
            context,
            "lip.socket.composition",
            COMPOSITION_PATH,
            "PyYAML is required to read the Host composition",
        )
        return
    try:
        text = composition_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        _error(
            context,
            "lip.socket.composition",
            COMPOSITION_PATH,
            f"cannot read composition: {exc}",
        )
        return
    try:
        composition = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        _error(
            context,
            "lip.socket.composition",
            COMPOSITION_PATH,
            f"cannot parse composition: {exc}",
        )
        return
    sockets = composition.get("sockets", {}) if isinstance(composition, dict) else None
    if not isinstance(sockets, dict):
        _error(
            context,
            "lip.socket.composition",
            COMPOSITION_PATH,
            "composition sockets must be a mapping",
        )
        return
    for socket, plugs in sockets.items():
        if not isinstance(plugs, dict):
            _error(
                context,
                "lip.socket.path",
                COMPOSITION_PATH,
                f"socket `{socket}` must map plug names to file paths",
            )
            continue
        for name, raw_path in plugs.items():
            rel = str(raw_path).replace("\\", "/")
            path = repo / rel
            if not path.is_file():
                _error(
                    context,
                    "lip.socket.path",
                    rel,
                    f"socket `{socket}` plug `{name}` is missing",
                )
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
            except (OSError, UnicodeError, SyntaxError) as exc:
                _error(context, "lip.socket.plugin_name", rel, f"cannot parse plug: {exc}")
                continue
            plugin_name = _const(tree, "PLUGIN_NAME")
            if plugin_name != str(name):
                _error(
                    context,
                    "lip.socket.plugin_name",
                    rel,
                    f"PLUGIN_NAME must be the static string `{name}`",
                )
    _check_modules(context, repo, composition)
    _check_composers(context, repo, composition)


def _check_modules(
    context: dict[str, Any],
    repo: Path,
    composition: dict[str, Any],
) -> None:
    modules = composition.get("modules", {})
    if not isinstance(modules, dict):
        _error(
            context,
            "lip.module.composition",
            COMPOSITION_PATH,
            "composition modules must map plugin names to file paths",
        )
        return
    for name, raw_path in modules.items():
        _check_named_module(
            context,
            repo,
            str(name),
            raw_path,
            rule="lip.module",
            require_apply=False,
        )


def _check_composers(
    context: dict[str, Any],
    repo: Path,
    composition: dict[str, Any],
) -> None:
    plugins = composition.get("plugins", [])
    if not isinstance(plugins, list):
        _error(
            context,
            "lip.composer.composition",
            COMPOSITION_PATH,
            "composition plugins must be a list",
        )
        return
    for entry in plugins:
        if not isinstance(entry, dict):
            _error(
                context,
                "lip.composer.composition",
                COMPOSITION_PATH,
                "each composition plugin must be a mapping",
            )
            continue
        name = entry.get("name")
        path = entry.get("path")
        if not isinstance(name, str) or not name:
            _error(
                context,
                "lip.composer.name",
                COMPOSITION_PATH,
                "each composition plugin needs a non-empty name",
            )
            continue
        if "socket" in entry:
            _error(
                context,
                "lip.composer.source",
                COMPOSITION_PATH,
                f"composer `{name}` cannot use socket; Recipes require path",
            )
            continue
        _check_named_module(
            context,
            repo,
            name,
            path,
            rule="lip.composer",
            require_apply=True,
        )


def _check_named_module(
    context: dict[str, Any],
    repo: Path,
    name: str,
    raw_path: Any,
    *,
    rule: str,
    require_apply: bool,
) -> None:
    if not isinstance(raw_path, str) or not raw_path:
        _error(
            context,
            f"{rule}.path",
            COMPOSITION_PATH,
            f"`{name}` must map to a non-empty file path",
        )
        return
    rel = raw_path.replace("\\", "/")
    path = repo / rel
    if not path.is_file():
        _error(context, f"{rule}.path", rel, f"configured module `{name}` is missing")
        return
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except (OSError, UnicodeError, SyntaxError) as exc:
        _error(context, f"{rule}.source", rel, f"cannot parse module: {exc}")
        return
    if _const(tree, "PLUGIN_NAME") != name:
        _error(
            context,
            f"{rule}.plugin_name",
            rel,
            f"PLUGIN_NAME must be the static string `{name}`",
        )
    if require_apply and not any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "apply"
        for node in tree.body
    ):
        _error(
            context,
            f"{rule}.apply",
            rel,
            f"composer `{name}` must define apply(lip, config)",
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
                f"leaf plugins must not import `{engine}`; Host looks up sockets by name",
            )


def _iter_family_files(
    repo: Path, families: Iterable[dict[str, Any]]
) -> list[tuple[str, Path]]:
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


def _error(context: dict[str, Any], rule: str, path: str, detail: str) -> None:
    context["violations"].append(
        {"rule": rule, "path": path, "detail": detail, "severity": "error"}
    )
