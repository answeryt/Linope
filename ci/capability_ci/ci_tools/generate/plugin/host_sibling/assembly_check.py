# -*- coding: utf-8 -*-
"""Host-sibling check: composers must use cap-bus injection boundaries.

A composer is a file outside the compose engine that imports capability graph
APIs. It may wire inject / CapBus / Capability / FunctionModelAdapter from
capability.model; it must not reimplement discovery or reflective dispatch.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


PLUGIN_NAME = "plugin_assembly"
PLUGIN_VERSION = "1.0"

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    "pypyr-main",
    "faststream-main",
    "temporal-sdk-python",
    "restate-sdk-python",
    "dbos-transact-py",
    "temporal",
    "restate",
}
SKIP_PREFIXES = (
    "kernel/compose/",
    "tests/kernel/",
)
COMPOSER_NAMES = frozenset(
    {"CapabilityCatalog", "CapabilityGraphResolver", "ComposeSpec"}
)
SOURCE_NAMES = frozenset(
    {"inject", "inject_capabilities", "CapBus", "Capability"}
)
FALLBACK_ABI = frozenset(
    {
        "is_output_cap_error",
        "parse_available_output_tokens_from_error",
        "resolve_lower_context_limit_from_error",
        "get_next_context_probe_tier",
    }
)


def run(context: dict[str, Any]) -> dict[str, Any]:
    repo = Path(context["repo_root"])
    if not repo.is_dir():
        return context
    for rel, tree in _iter_python(repo):
        if not _is_composer(tree):
            continue
        _check_composer(context, rel, tree)
    return context


def _check_composer(context: dict[str, Any], rel: str, tree: ast.AST) -> None:
    imported = _imported_names(tree)
    if not (imported & SOURCE_NAMES):
        _error(
            context,
            "assembly.source.required",
            rel,
            "composer must use inject, inject_capabilities, CapBus, or Capability",
        )
    if _calls_ast_parse(tree):
        _error(
            context,
            "assembly.source.ast_parse",
            rel,
            "composer must not call ast.parse; discovery belongs to compose Sources",
        )
    if _defines_discover(tree):
        _error(
            context,
            "assembly.source.discover",
            rel,
            "composer must not define discover(); use inject or CapBus",
        )
    if _calls_inspect_signature(tree) and not _uses_function_model_adapter(tree):
        _error(
            context,
            "assembly.bind.signature",
            rel,
            "composer must not call inspect.signature; FunctionModelAdapter binds call_api",
        )
    if _uses_fallback_abi(tree):
        _error(
            context,
            "assembly.fallback.abi",
            rel,
            "composer must not duck-type fallback helpers; leaves expose recover()",
        )
    if _imports_kernel_services(tree):
        _error(
            context,
            "assembly.bridge.kernel_services",
            rel,
            "composer must not import kernel.compose.capability.services; use CapBus",
        )
    if _calls_register_adapter(tree):
        _error(
            context,
            "assembly.bridge.adapter",
            rel,
            "composer must not register into a domain registry; publish on CapBus",
        )
    if _defines_local_adapter(tree):
        _error(
            context,
            "assembly.bridge.local_adapter",
            rel,
            "composer must not define a local Adapter with stream()",
        )
    if _imports_function_model_adapter(tree) and not _adapter_from_capability_model(tree):
        _error(
            context,
            "assembly.bridge.adapter_source",
            rel,
            "FunctionModelAdapter must come from capability.model, not kernel",
        )
    if _uses_dynamic_member_dispatch(tree):
        _error(
            context,
            "assembly.bind.dynamic_dispatch",
            rel,
            "composer must not reflect members and dynamically dispatch leaf call details",
        )
    if _defines_kind_map(tree):
        _error(
            context,
            "assembly.kind.local_map",
            rel,
            "composer must not translate kind; cluster kind is plugin-declared",
        )
    if _scans_capability_prefix(tree):
        _error(
            context,
            "assembly.nodes.prefix",
            rel,
            "composer must use ctx.get_all(capability); do not scan key prefixes",
        )


def _iter_python(repo: Path) -> list[tuple[str, ast.AST]]:
    result: list[tuple[str, ast.AST]] = []
    for path in sorted(repo.rglob("*.py")):
        if any(_skip_dir(part) for part in path.parts):
            continue
        try:
            rel = path.relative_to(repo).as_posix()
        except ValueError:
            continue
        if _skip_prefix(rel):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, UnicodeError, SyntaxError):
            continue
        result.append((rel, tree))
    return result


def _is_composer(tree: ast.AST) -> bool:
    return bool(_imported_names(tree) & COMPOSER_NAMES)


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.rsplit(".", 1)[-1])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _defines_function_model_adapter(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.ClassDef) and node.name == "FunctionModelAdapter"
        for node in ast.walk(tree)
    )


def _uses_function_model_adapter(tree: ast.AST) -> bool:
    return "FunctionModelAdapter" in _imported_names(tree) or _defines_function_model_adapter(
        tree
    )


def _imports_function_model_adapter(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        names = {alias.asname or alias.name for alias in node.names}
        if "FunctionModelAdapter" in names:
            return True
    return False


def _adapter_from_capability_model(tree: ast.AST) -> bool:
    if _defines_function_model_adapter(tree):
        return True
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        names = {alias.asname or alias.name for alias in node.names}
        if "FunctionModelAdapter" not in names:
            continue
        if (node.module or "").startswith("capability.model"):
            return True
    return False


def _imports_kernel_services(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "kernel.compose.capability.services"
        ):
            return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("kernel.compose.capability.services"):
                    return True
    return False


def _calls_ast_parse(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "parse":
            return True
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "parse"
            and isinstance(func.value, ast.Name)
            and func.value.id == "ast"
        ):
            return True
    return False


def _defines_discover(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "discover":
                return True
    return False


def _calls_inspect_signature(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "signature"
            and isinstance(func.value, ast.Name)
            and func.value.id == "inspect"
        ):
            return True
    return False


def _uses_fallback_abi(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value in FALLBACK_ABI:
            return True
        if isinstance(node, ast.Name) and node.id in FALLBACK_ABI:
            return True
        if isinstance(node, ast.Attribute) and node.attr in FALLBACK_ABI:
            return True
    return False


def _calls_register_adapter(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "register_adapter":
            return True
        if isinstance(func, ast.Name) and func.id == "register_adapter":
            return True
    return False


def _register_adapter_uses_function_adapter(tree: ast.AST) -> bool:
    aliases = _function_adapter_aliases(tree)
    seen = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_register_adapter_call(node):
            continue
        seen = True
        adapter = _adapter_argument(node)
        if adapter is None:
            return False
        if isinstance(adapter, ast.Call) and _is_function_model_adapter_call(adapter):
            continue
        if isinstance(adapter, ast.Name) and adapter.id in aliases:
            continue
        return False
    return seen


def _function_adapter_aliases(tree: ast.AST) -> set[str]:
    aliases: set[str] = set()
    for node in ast.walk(tree):
        value = None
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            value = node.value
            target = node.targets[0]
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            target = node.target
        if (
            isinstance(target, ast.Name)
            and isinstance(value, ast.Call)
            and _is_function_model_adapter_call(value)
        ):
            aliases.add(target.id)
    return aliases


def _is_function_model_adapter_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "FunctionModelAdapter"
    if isinstance(func, ast.Attribute):
        return func.attr == "FunctionModelAdapter"
    return False


def _is_register_adapter_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr == "register_adapter"
    if isinstance(func, ast.Name):
        return func.id == "register_adapter"
    return False


def _adapter_argument(node: ast.Call) -> ast.AST | None:
    if len(node.args) >= 2:
        return node.args[1]
    for keyword in node.keywords:
        if keyword.arg == "adapter":
            return keyword.value
    return None


def _defines_local_adapter(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name == "FunctionModelAdapter" or not node.name.endswith("Adapter"):
            continue
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "stream":
                return True
    return False


def _uses_dynamic_member_dispatch(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)):
            continue
        if not _loop_scans_members(node):
            continue
        selector_names = _target_names(node.target)
        dispatch_names = set(selector_names)
        dispatch_names.update(_loop_getattr_aliases(node, selector_names))
        if not dispatch_names:
            continue
        if _calls_startswith(node) and _calls_named_function(node, dispatch_names):
            return True
    return False


def _loop_scans_members(node: ast.For | ast.AsyncFor) -> bool:
    iterator = node.iter
    if not isinstance(iterator, ast.Call):
        return False
    if _is_member_scan_call(iterator):
        return True
    if isinstance(iterator.func, ast.Attribute) and iterator.func.attr in {"items", "keys", "values"}:
        value = iterator.func.value
        return isinstance(value, ast.Call) and _is_member_scan_call(value)
    return False


def _is_member_scan_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in {"vars", "dir"}
    if isinstance(func, ast.Attribute):
        return func.attr == "getmembers"
    return False


def _target_names(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for item in target.elts:
            names.update(_target_names(item))
        return names
    return set()


def _loop_getattr_aliases(node: ast.For | ast.AsyncFor, selector_names: set[str]) -> set[str]:
    aliases: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Assign) or len(child.targets) != 1:
            continue
        target = child.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = child.value
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "getattr"
            and len(value.args) >= 2
            and isinstance(value.args[1], ast.Name)
            and value.args[1].id in selector_names
        ):
            aliases.add(target.id)
    return aliases


def _calls_named_function(tree: ast.AST, names: set[str]) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in names:
            return True
    return False


def _defines_kind_map(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "_DOMAIN_KIND":
            return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_DOMAIN_KIND":
                    return True
    return False


def _scans_capability_prefix(tree: ast.AST) -> bool:
    if not _calls_capabilities(tree) or not _calls_startswith(tree):
        return False
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.endswith(".")
            and "." in node.value[:-1]
        ):
            return True
        if isinstance(node, ast.JoinedStr):
            pieces = [
                value.value
                for value in node.values
                if isinstance(value, ast.Constant)
            ]
            if any(isinstance(piece, str) and piece.endswith(".") for piece in pieces):
                return True
    return False


def _calls_startswith(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "startswith"
        ):
            return True
    return False


def _calls_capabilities(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "capabilities":
            return True
        if isinstance(func, ast.Attribute) and func.attr == "capabilities":
            return True
    return False


def _skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.startswith(".") or name.endswith("-main")


def _skip_prefix(rel: str) -> bool:
    if rel.startswith("kernel/compose/") or rel == "kernel/compose":
        return True
    if rel.startswith("tests/kernel/") or rel == "tests/kernel":
        return True
    return any(rel.startswith(prefix) for prefix in SKIP_PREFIXES)


def _error(context: dict[str, Any], rule: str, path: str, detail: str) -> None:
    context["violations"].append(
        {"rule": rule, "path": path, "detail": detail, "severity": "error"}
    )
