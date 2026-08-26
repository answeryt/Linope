# -*- coding: utf-8 -*-
"""Host-sibling check for the Process-driven Service + Resources kernel.

Layer and injection inventory comes from the allow-list card. This file
only walks ``kernel/`` and appends violations. Isolation stays in deny_check.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


PLUGIN_NAME = "plugin_kernel"
PLUGIN_VERSION = "1.0"

SKIP_DIR_NAMES = {"__pycache__", ".git", "node_modules"}
EXCLUDE_TOP = frozenset({"check"})
CORE_PREFIXES = (
    "kernel/process/",
    "kernel/thred/",
    "kernel/resource/",
)
OS_MODULES = frozenset({"multiprocessing", "subprocess", "threading", "concurrent"})
DEPLOY_MODULES = frozenset({"fastapi", "faststream", "starlette", "uvicorn", "redis"})
LLM_PROVIDER_MODULES = frozenset(
    {"anthropic", "cohere", "genai", "litellm", "mistralai", "ollama", "openai", "transformers"}
)
LLM_PROVIDER_PREFIXES = ("google.genai", "google.generativeai")
LLM_EXECUTOR_NAMES = frozenset(
    {
        "_echo_model",
        "call_model",
        "invoke_model",
        "llm_client",
        "llm_handler",
        "model_client",
        "model_handler",
    }
)
def run(context: dict[str, Any]) -> dict[str, Any]:
    repo = Path(context["repo_root"])
    kernel = repo / "kernel"
    if not kernel.is_dir():
        return context
    card = context.get("allow_list") or {}
    layers = _string_lists(card.get("kernel_layers"))
    inject = _string_lists(card.get("inject"))
    if not layers:
        _error(context, "kernel.layer.toplevel", "kernel", "allow list is missing kernel_layers")
        return context
    _check_tree(context, repo, kernel, layers)
    for rel, path, tree in _iter_py(repo, kernel):
        if path.name.endswith("_plugin.py"):
            name = _const(tree, "PLUGIN_NAME")
            if name and not name.startswith("kernel_"):
                _error(context, "kernel.vocab.plugin_prefix", rel, "PLUGIN_NAME must start with `kernel_`")
        if _under(rel, CORE_PREFIXES) and not _under(rel, ("kernel/thred/plugin/",)):
            _check_imports(context, rel, tree)
        if rel.endswith("process_state_plugin.py"):
            _require_keys(
                context,
                rel,
                tree,
                "build_process_run",
                (
                    "process_id",
                    "run_id",
                    "process_type",
                    "definition_version",
                    "state",
                    "pending_activations",
                    "resource_leases",
                ),
                "kernel.role.process_run_fields",
            )
        if rel.endswith("activation_envelope_plugin.py"):
            _require_keys(
                context,
                rel,
                tree,
                "normalize_activation",
                ("activation_id", "process_id", "process_type", "input"),
                "kernel.role.activation_fields",
            )
        stem = path.stem.removesuffix("_plugin")
        required = inject.get(stem) or inject.get(path.stem)
        if required:
            _check_inject(context, rel, tree, tuple(required))
    return context


def _check_tree(
    context: dict[str, Any],
    repo: Path,
    kernel: Path,
    layers: dict[str, list[str]],
) -> None:
    allowed_top = set(layers) | EXCLUDE_TOP
    for child in kernel.iterdir():
        if (
            child.is_dir()
            and not _skip(child.name)
            and child.name not in allowed_top
            and any(child.rglob("*_plugin.py"))
        ):
            _error(context, "kernel.layer.toplevel", f"kernel/{child.name}", "not a contracted kernel layer")
    allowed_leaves: set[str] = set()
    for layer, children in layers.items():
        root = kernel / layer
        if not root.is_dir():
            _error(context, "kernel.layer.children", f"kernel/{layer}", "contracted layer is missing")
            continue
        allow = set(children)
        for child in root.iterdir():
            if (
                child.is_dir()
                and not _skip(child.name)
                and child.name not in allow
                and any(child.rglob("*_plugin.py"))
            ):
                _error(context, "kernel.layer.children", f"kernel/{layer}/{child.name}", f"not in `{layer}` allow list")
        allowed_leaves.update(f"kernel/{layer}/{name}" for name in children)
    for path in kernel.rglob("*_plugin.py"):
        if any(_skip(part) for part in path.parts):
            continue
        rel = path.relative_to(repo).as_posix()
        parent = path.parent.relative_to(repo).as_posix()
        if parent not in allowed_leaves:
            _error(context, "kernel.layer.leaf_plugin", rel, "plugin must live in a contracted leaf directory")
def _string_lists(raw: Any) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, value in raw.items():
        if isinstance(value, (list, tuple)):
            result[str(key)] = [str(item) for item in value]
        elif value:
            result[str(key)] = [str(value)]
    return result


def _check_inject(
    context: dict[str, Any],
    rel: str,
    tree: ast.AST,
    required: tuple[str, ...],
) -> None:
    params: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            params.add(arg.arg)
    missing = [name for name in required if name not in params]
    if missing:
        _error(
            context,
            "kernel.inject.required",
            rel,
            "Host must inject " + ", ".join(f"`{name}`" for name in missing),
        )


def _check_imports(context: dict[str, Any], rel: str, tree: ast.AST) -> None:
    for node in ast.walk(tree):
        roots = _import_roots(node)
        os_hit = roots & OS_MODULES
        if os_hit:
            rule = "kernel.role.os_process" if os_hit & {"multiprocessing", "subprocess"} else "kernel.role.os_thread"
            _error(context, rule, rel, "OS workers belong in kernel/services/worker, not " + ", ".join(sorted(os_hit)))
        deploy = roots & DEPLOY_MODULES
        if deploy:
            _error(context, "kernel.role.deploy_api", rel, "deploy APIs belong in kernel/services, not " + ", ".join(sorted(deploy)))


def _require_fns(context: dict[str, Any], rel: str, tree: ast.AST, names: tuple[str, ...], rule: str) -> None:
    found = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for name in names:
        if name not in found:
            _error(context, rule, rel, f"missing `{name}`")


def _require_keys(
    context: dict[str, Any],
    rel: str,
    tree: ast.AST,
    func: str,
    required: tuple[str, ...],
    rule: str,
) -> None:
    constants = _string_constants(tree)
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != func:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Dict):
                for key in child.keys:
                    text = _key_text(key, constants)
                    if text:
                        keys.add(text)
    missing = [name for name in required if name not in keys]
    if missing:
        _error(context, rule, rel, f"`{func}` must write " + ", ".join(f"`{name}`" for name in missing))


def _iter_py(repo: Path, kernel: Path) -> list[tuple[str, Path, ast.AST]]:
    result: list[tuple[str, Path, ast.AST]] = []
    for path in sorted(kernel.rglob("*.py")):
        if any(_skip(part) for part in path.parts):
            continue
        rel = path.relative_to(repo).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, UnicodeError, SyntaxError):
            continue
        result.append((rel, path, tree))
    return result


def _string_constants(tree: ast.AST) -> dict[str, str]:
    result: dict[str, str] = {}
    for node in tree.body if isinstance(tree, ast.Module) else []:
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            result[target.id] = value.value
    return result


def _const(tree: ast.AST, name: str) -> str | None:
    return _string_constants(tree).get(name)


def _key_text(node: ast.AST | None, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _import_roots(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Import):
        return {alias.name.split(".", 1)[0] for alias in node.names if alias.name}
    if isinstance(node, ast.ImportFrom) and node.module:
        return {node.module.split(".", 1)[0]}
    return set()


def _imported(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names if alias.name]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module]
    return []


def _call_tail(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _under(rel: str, prefixes: tuple[str, ...]) -> bool:
    return any(rel.startswith(prefix) for prefix in prefixes)


def _skip(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.startswith(".")


def _error(context: dict[str, Any], rule: str, path: str, detail: str) -> None:
    context["violations"].append({"rule": rule, "path": path, "detail": detail, "severity": "error"})
