# -*- coding: utf-8 -*-
"""Host for plugin-conformance CI.

This file is the composition layer, not a check plugin. It discovers
``*_check.py`` and ``*_generate.py`` files under ``list/deny_list``,
``list/allow_list``, and ``host_sibling``, then loads them with importlib the
same way pypyr loads steps by name — there is no static import of those
plugins.

Each check plugin receives a shared context dict and appends violations.
Generate plugins write allow/deny list cards in ``--format``. ``--check``
fails when a committed list card is stale, or when any error-severity
violation exists.

Families are walked from ``PROJECT_TOPLEVEL`` on disk. The only handwritten
inventory is the allow-list card. The deny list is generated as discovered
families minus those allow-list paths.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

PLUGIN_NAME = "plugin_generate_host"
PLUGIN_VERSION = "1.0"
LIST_FORMATS = ("json", "yaml", "toml", "md")
LIST_FORMAT_ALIASES = {"yml": "yaml", "markdown": "md"}

PROJECT_TOPLEVEL = ("model", "context", "prompt", "tools", "kernel")

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    "pypyr-main",
}

PROVIDER_HINT_KEYS = ("provider", "interface")


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up until plugin-family roots and the isolation allowlist are visible."""
    current = (start or Path(__file__).resolve()).parent
    for candidate in (current, *current.parents):
        gates = candidate / ".gates" / "isolation-allowlist.json"
        model = candidate / "model"
        tools = candidate / "tools"
        if gates.is_file() and model.is_dir() and tools.is_dir():
            return candidate
        if (candidate / "model").is_dir() and (candidate / "context").is_dir():
            return candidate
    return Path(__file__).resolve().parents[5]


def load_allowlist(repo: Path) -> list[tuple[str, str]]:
    path = repo / ".gates" / "isolation-allowlist.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    edges = payload.get("edges", payload) if isinstance(payload, dict) else payload
    result: list[tuple[str, str]] = []
    for edge in edges or []:
        if isinstance(edge, (list, tuple)) and len(edge) >= 2:
            result.append((str(edge[0]).replace("\\", "/"), str(edge[1])))
    return result


def discover_families(repo: Path) -> list[dict[str, Any]]:
    """Walk project roots and collect directories that look like plugin families."""
    dirs: set[str] = set()
    for top in PROJECT_TOPLEVEL:
        base = repo / top
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if _should_skip(repo, path):
                continue
            if path.is_file() and path.suffix == ".py":
                dirs.add(path.parent.relative_to(repo).as_posix())
            elif path.is_file() and path.suffix.lower() == ".json" and _is_provider_json(path):
                parent = path.parent.parent
                try:
                    rel = parent.relative_to(repo).as_posix()
                except ValueError:
                    continue
                if rel and rel != ".":
                    dirs.add(rel)

    families: list[dict[str, Any]] = []
    for rel in sorted(dirs):
        nested = [other for other in dirs if other.startswith(rel + "/")]
        if nested and not _has_direct_python(repo / rel) and not _dir_has_provider_config(repo / rel):
            continue
        families.append({"id": Path(rel).name, "root": rel})
    _assign_family_files(repo, families)
    return families


def partition_families(
    families: list[dict[str, Any]],
    allow_paths: Iterable[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deny set is discovered families minus allow-list paths."""
    patterns = [str(item).replace("\\", "/") for item in allow_paths]
    denied: list[dict[str, Any]] = []
    allowed: list[dict[str, Any]] = []
    for family in families:
        root = str(family["root"]).replace("\\", "/")
        original_files = list(family.get("files") or [])
        if _matches_allow(root, patterns):
            allowed.append(family)
            continue
        files = [
            name
            for name in original_files
            if not _matches_allow(f"{root}/{name}".replace("\\", "/"), patterns)
        ]
        if original_files and not files:
            allowed.append(family)
            continue
        denied.append({**family, "files": files})
    return denied, allowed


def _matches_allow(rel: str, patterns: Iterable[str]) -> bool:
    rel = rel.replace("\\", "/")
    for raw in patterns:
        pat = str(raw).replace("\\", "/").rstrip("/")
        if not pat:
            continue
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, pat + "/*"):
            return True
        if rel == pat or rel.startswith(pat + "/"):
            return True
    return False


def _assign_family_files(repo: Path, families: list[dict[str, Any]]) -> None:
    roots = sorted((family["root"] for family in families), key=len, reverse=True)
    for family in families:
        root_path = repo / family["root"]
        owned: list[str] = []
        if root_path.is_dir():
            for path in sorted(root_path.rglob("*.py")):
                if _should_skip(repo, path):
                    continue
                rel = path.relative_to(repo).as_posix()
                owner = next(
                    (root for root in roots if rel == root or rel.startswith(root + "/")),
                    None,
                )
                if owner == family["root"]:
                    owned.append(path.relative_to(root_path).as_posix())
        family["files"] = owned


def _should_skip(repo: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(repo).parts
    except ValueError:
        parts = path.parts
    return any(part in SKIP_DIR_NAMES or part.startswith(".") for part in parts)


def _has_direct_python(path: Path) -> bool:
    if not path.is_dir():
        return False
    for child in path.iterdir():
        if child.name in SKIP_DIR_NAMES or child.name.startswith("."):
            continue
        if child.is_file() and child.suffix == ".py":
            return True
    return False


def _is_provider_json(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and all(key in payload for key in PROVIDER_HINT_KEYS)


def _dir_has_provider_config(path: Path) -> bool:
    if not path.is_dir():
        return False
    for child in path.rglob("*.json"):
        if any(part in SKIP_DIR_NAMES for part in child.parts):
            continue
        if _is_provider_json(child):
            return True
    return False


def load_plugin(path: Path) -> ModuleType:
    """Load a check or generate plugin by file path. Mirrors pypyr step_cache loading."""
    spec = importlib.util.spec_from_file_location(
        f"plugin_generate_plugin_{path.stem}",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load plugin: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_check_plugins(here: Path) -> list[Path]:
    """Deny list first, then allow list, then Host-sibling checks."""
    return [
        *_named_plugins(here / "list" / "deny_list", "*_check.py"),
        *_named_plugins(here / "list" / "allow_list", "*_check.py"),
        *_named_plugins(here / "host_sibling", "*_check.py"),
    ]


def discover_generate_plugins(here: Path) -> list[Path]:
    """Allow list first so handwritten inventory is emitted before deny cards."""
    return [
        *_named_plugins(here / "list" / "allow_list", "*_generate.py"),
        *_named_plugins(here / "list" / "deny_list", "*_generate.py"),
    ]


def _named_plugins(directory: Path, pattern: str) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob(pattern) if path.is_file())


def normalize_list_format(raw: str | None) -> str:
    name = str(raw or "json").lower().lstrip(".")
    name = LIST_FORMAT_ALIASES.get(name, name)
    if name not in LIST_FORMATS:
        raise ValueError(f"unsupported list format: {raw}")
    return name


def load_allow_list(here: Path, fmt: str) -> dict[str, Any]:
    path = here / "list" / "allow_list" / "allow_list_generate.py"
    if not path.is_file():
        return {}
    module = load_plugin(path)
    loader = getattr(module, "load", None)
    if not callable(loader):
        return {}
    payload = loader(fmt)
    return payload if isinstance(payload, dict) else {}


def _dedupe_violations(context: dict[str, Any]) -> None:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in context.get("violations") or []:
        key = (
            str(item.get("rule", "")),
            str(item.get("path", "")),
            str(item.get("detail", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    context["violations"] = sorted(
        unique,
        key=lambda item: (
            item.get("rule", ""),
            item.get("path", ""),
            item.get("detail", ""),
        ),
    )


def _print_errors(errors: list[dict[str, Any]]) -> None:
    sys.stderr.write(f"plugin_generate: {len(errors)} plugin convention error(s).\n")
    for item in errors:
        sys.stderr.write(
            f"- `{item.get('rule')}` `{item.get('path')}`: {item.get('detail')}\n"
        )


def build_context(
    repo: Path,
    here: Path | None = None,
    fmt: str = "json",
) -> dict[str, Any]:
    here = here or Path(__file__).resolve().parent
    allow_list = load_allow_list(here, fmt)
    allow_paths = [
        str(item)
        for item in (allow_list.get("paths") or allow_list.get("except") or [])
    ]
    discovered = discover_families(repo)
    denied, allowed = partition_families(discovered, allow_paths)
    return {
        "repo_root": str(repo),
        "families": denied,
        "allowed_families": allowed,
        "project_toplevel": list(PROJECT_TOPLEVEL),
        "allowlist": load_allowlist(repo),
        "deny_list": {"families": [family["root"] for family in denied]},
        "allow_list": allow_list,
        "format": fmt,
        "violations": [],
        "file_count": 0,
        "facts": {},
        "stale": [],
        "generated": [],
    }


def run_plugins(context: dict[str, Any], paths: list[Path]) -> dict[str, Any]:
    for path in paths:
        module = load_plugin(path)
        run = getattr(module, "run", None)
        if not callable(run):
            raise AttributeError(f"{path.name} is missing run(context)")
        returned = run(context)
        if isinstance(returned, dict):
            context = returned
        context.setdefault("facts", {})[path.stem] = getattr(
            module, "PLUGIN_NAME", path.stem
        )
    return context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check independent plugin conventions for this repository.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when a committed list card is stale or when errors exist.",
    )
    parser.add_argument(
        "--format",
        choices=(*LIST_FORMATS, *LIST_FORMAT_ALIASES),
        default="json",
        help="Allow/deny list card format. Default: json.",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Repository root. Default: walk up from this file.",
    )
    args = parser.parse_args(argv)

    try:
        fmt = normalize_list_format(args.format)
    except ValueError as exc:
        parser.error(str(exc))

    here = Path(__file__).resolve().parent
    repo = Path(args.root).resolve() if args.root else find_repo_root(here)
    context = build_context(repo, here, fmt)
    context["check"] = bool(args.check)
    context = run_plugins(context, discover_check_plugins(here))
    context = run_plugins(context, discover_generate_plugins(here))
    _dedupe_violations(context)
    errors = [
        item for item in context.get("violations") or []
        if item.get("severity") == "error"
    ]
    stale = list(context.get("stale") or [])

    if args.check:
        if stale:
            sys.stderr.write(
                "plugin_generate: generated list cards are stale. "
                "Run plugin_generate.py and commit the allow/deny list cards.\n"
            )
            for item in stale:
                sys.stderr.write(f"- {item}\n")
            return 1
        if errors:
            _print_errors(errors)
            return 1
        sys.stdout.write("plugin_generate: generated artifacts are up to date.\n")
        return 0

    written = list(context.get("generated") or [])
    if written:
        sys.stdout.write("plugin_generate: wrote " + ", ".join(written) + "\n")
    else:
        sys.stdout.write("plugin_generate: no list cards written\n")
    sys.stdout.flush()
    if errors:
        _print_errors(errors)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
