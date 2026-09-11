# -*- coding: utf-8 -*-
"""Host-sibling check: plugin-declared cluster kinds stay open and consistent.

Kind is a dotted cluster owned by the leaf (``model.interface``,
``context.compression``). This check does not whitelist model roles. Install
strategy is inferred by compose; leftover install words are not valid kinds.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any


PLUGIN_NAME = "plugin_descriptor"
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
    "tests",
    "test",
}
SKIP_PREFIXES = (
    "kernel/compose/",
    "tests/",
    "capability/contract/",
    "contract/",
    "tools/external_tools/ci_tools/",
    "capability/tools/external_tools/ci_tools/",
)
MANIFEST_NAMES = ("plugin.json", "plugin.toml", "plugin.yaml", "plugin.yml")
INSTALL_KINDS = frozenset(
    {
        "recipe",
        "module",
        "tool",
        "model",
        "capability",
        "pipeline",
        "transform",
        "entry_point",
        "model_adapter",
    }
)


def run(context: dict[str, Any]) -> dict[str, Any]:
    repo = Path(context["repo_root"])
    if not repo.is_dir():
        return context
    for rel, path in _iter_files(repo):
        if path.suffix == ".py":
            _check_python(context, repo, rel, path)
        elif path.name in MANIFEST_NAMES:
            _check_manifest(context, repo, rel, path)
    return context


def _check_python(context: dict[str, Any], repo: Path, rel: str, path: Path) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
    except (OSError, UnicodeError, SyntaxError) as exc:
        _error(context, "descriptor.parse", rel, f"cannot parse plugin: {exc}")
        return
    payload = _capability_dict(tree)
    if payload is None:
        return
    if _imports_capability_contract(tree):
        _error(
            context,
            "descriptor.contract_import",
            rel,
            "leaves must not import capability.contract; declare a literal CAPABILITY dict",
        )
    _check_payload(context, repo, rel, payload, source_path=path, functions=_functions(tree))


def _check_manifest(context: dict[str, Any], repo: Path, rel: str, path: Path) -> None:
    try:
        payload = _read_manifest(path)
    except (OSError, UnicodeError, ValueError) as exc:
        _error(context, "descriptor.parse", rel, f"cannot read plugin manifest: {exc}")
        return
    source = payload.get("source")
    source_path = None
    if isinstance(source, str) and source:
        candidate = (path.parent / source).resolve()
        source_path = candidate if candidate.is_file() else None
        if source_path is None:
            _error(
                context,
                "descriptor.entry",
                rel,
                f"source {source!r} does not exist",
            )
    functions = _functions(_parse_optional(source_path)) if source_path else set()
    _check_payload(context, repo, rel, payload, source_path=source_path, functions=functions)


def _check_payload(
    context: dict[str, Any],
    repo: Path,
    rel: str,
    payload: dict[str, Any],
    *,
    source_path: Path | None,
    functions: set[str],
) -> None:
    kind = payload.get("kind")
    if not isinstance(kind, str) or not kind:
        _error(context, "descriptor.kind", rel, "kind must be a non-empty cluster string")
        return
    if kind in INSTALL_KINDS:
        _error(
            context,
            "descriptor.kind.install_word",
            rel,
            f"kind {kind!r} is an install word; declare a cluster such as model.thread",
        )
        return
    name = payload.get("name")
    provides = _strings(payload.get("provides"))
    if not _in_cluster(kind, name, provides):
        _error(
            context,
            "descriptor.kind.cluster",
            rel,
            "name or provides must start with kind or its cluster prefix",
        )
    try:
        _parse_requires(payload.get("requires", ()))
    except (TypeError, ValueError) as exc:
        _error(context, "descriptor.requires", rel, str(exc))
    entry = payload.get("entry")
    if isinstance(entry, str) and entry:
        if source_path is None:
            _error(context, "descriptor.entry", rel, f"entry {entry!r} needs a source file")
        elif entry not in functions:
            _error(
                context,
                "descriptor.entry",
                rel,
                f"entry {entry!r} is missing from {source_path.relative_to(repo).as_posix() if _under(repo, source_path) else source_path.name}",
            )


def _parse_requires(value: Any) -> None:
    """Same grammar as kernel.compose.capability.contracts.parse_requirements."""

    if value is None:
        return
    if isinstance(value, str):
        value = [value]
    if isinstance(value, dict):
        value = [
            {"capability": name, **(settings if isinstance(settings, dict) else {})}
            for name, settings in value.items()
        ]
    if not isinstance(value, (list, tuple)):
        raise TypeError("capability requirements must be iterable")
    for item in value:
        if isinstance(item, str):
            if not item:
                raise ValueError("requirement capability must not be empty")
            continue
        if isinstance(item, dict):
            raw_name = item.get("capability", item.get("name"))
            if not isinstance(raw_name, str) or not raw_name:
                raise ValueError("requirement capability must be a non-empty string")
            cardinality = str(item.get("cardinality", "one"))
            if cardinality not in {"one", "many"}:
                raise ValueError(f"unsupported cardinality: {cardinality!r}")
            continue
        raise TypeError("requirements must contain strings or mappings")


def _in_cluster(kind: str, name: Any, provides: tuple[str, ...]) -> bool:
    cluster = kind.split(".", 1)[0]
    candidates = [*(provides or ()), name if isinstance(name, str) else ""]
    return any(
        value == kind
        or value.startswith(f"{kind}.")
        or value == cluster
        or value.startswith(f"{cluster}.")
        or value.startswith(cluster)
        for value in candidates
        if value
    )


def _capability_dict(tree: ast.AST) -> dict[str, Any] | None:
    constants: dict[str, Any] = {}
    for node in tree.body if isinstance(tree, ast.Module) else []:
        target = None
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if not isinstance(target, ast.Name) or value is None:
            continue
        try:
            constants[target.id] = ast.literal_eval(value)
        except (ValueError, TypeError):
            continue
    payload = constants.get("CAPABILITY")
    if not isinstance(payload, dict):
        payload = constants.get("MODEL_CAPABILITY")
    if isinstance(payload, dict):
        return payload
    return _capability_class_dict(tree)


def _capability_class_dict(tree: ast.AST) -> dict[str, Any] | None:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if not isinstance(node, ast.ClassDef) or not _extends_capability(node):
            continue
        payload: dict[str, Any] = {}
        for stmt in node.body:
            target = None
            value = None
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target, value = stmt.targets[0], stmt.value
            elif isinstance(stmt, ast.AnnAssign):
                target, value = stmt.target, stmt.value
            if not isinstance(target, ast.Name) or value is None:
                continue
            if target.id not in {
                "name",
                "version",
                "kind",
                "provides",
                "requires",
                "constraints",
                "entry",
                "config",
            }:
                continue
            try:
                payload[target.id] = ast.literal_eval(value)
            except (ValueError, TypeError):
                continue
        if isinstance(payload.get("name"), str) and payload["name"]:
            return payload
    return None


def _extends_capability(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Capability":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Capability":
            return True
    return False


def _functions(tree: ast.AST | None) -> set[str]:
    if tree is None:
        return set()
    return {
        node.name
        for node in tree.body
        if isinstance(tree, ast.Module)
        and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _parse_optional(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return None


def _read_manifest(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".json":
        payload = json.loads(text)
    elif suffix == ".toml":
        import tomllib

        payload = tomllib.loads(text)
    else:
        try:
            import yaml
        except ImportError as error:
            raise ValueError("PyYAML is required for YAML plugin manifests") from error
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError("plugin manifest must be a mapping")
    plugin = payload.get("plugin", payload)
    if not isinstance(plugin, dict):
        raise ValueError("plugin manifest [plugin] must be a mapping")
    return plugin


def _imports_capability_contract(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names if alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        for name in names:
            if name == "capability.contract" or name.startswith("capability.contract."):
                return True
            if name == "contract" or name.startswith("contract."):
                return True
    return False


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _iter_files(repo: Path) -> list[tuple[str, Path]]:
    result: list[tuple[str, Path]] = []
    for path in sorted(repo.rglob("*")):
        if not path.is_file():
            continue
        if any(_skip_dir(part) for part in path.parts):
            continue
        try:
            rel = path.relative_to(repo).as_posix()
        except ValueError:
            continue
        if _skip_prefix(rel):
            continue
        if path.suffix == ".py" or path.name in MANIFEST_NAMES:
            result.append((rel, path))
    return result


def _skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES or name.startswith(".") or name.endswith("-main")


def _skip_prefix(rel: str) -> bool:
    return any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in SKIP_PREFIXES)


def _under(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _error(context: dict[str, Any], rule: str, path: str, detail: str) -> None:
    context["violations"].append(
        {"rule": rule, "path": path, "detail": detail, "severity": "error"}
    )
