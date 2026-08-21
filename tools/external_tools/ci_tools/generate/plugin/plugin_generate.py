# -*- coding: utf-8 -*-
"""Host for plugin-conformance CI.

This file is the composition layer, not a check plugin. It discovers
``*_check.py`` files under ``list/deny_list``, ``list/allow_list``, and this
directory, then loads them with importlib the same way pypyr loads steps by
name — there is no static import of those plugins.

Each check plugin receives a shared context dict and appends violations.
``--check`` fails when the committed report is stale (gen-*.ts style) or when
any error-severity violation exists (pypyr assert style).

Families are scanned from disk via ``FAMILY_KIND_RULES``. A glob that matches
siblings (compression, prompt, MCP plugins) auto-includes new directories or
files; unique layout roots still declare a kind. ``assert_families_complete``
globs ``FAMILY_SCAN_GLOBS`` so an unclassified plugin path cannot stay silent.
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
REPORT_NAME = "plugin-conformance.md"

# Layout conventions used to classify scanned paths into families.
# Sibling globs grow automatically; a new unmatched path fails closed.
FAMILY_KIND_RULES: tuple[dict[str, Any], ...] = (
    {"glob": "context/context_compression/*", "kind": "compression"},
    {
        "glob": "model/model_API/model_paramaters/interface_paramaters",
        "kind": "apply_param",
    },
    {
        "glob": "model/model_API/model_paramaters/token_paramaters",
        "kind": "token",
    },
    {
        "glob": "model/model_API/model_paramaters/fallback_handlers",
        "kind": "fallback",
    },
    {"glob": "model/model_API/model_interface", "kind": "interface"},
    {"glob": "model/model_message", "kind": "message"},
    {"glob": "model/model_provider", "kind": "provider_config"},
    {
        "glob": "tools/external_tools/mcp/*_plugin.py",
        "kind": "mcp",
        "id": "mcp_plugins",
    },
    {"glob": "tools/external_tools/mcp/mcp_transport", "kind": "mcp_transport"},
    {
        "glob": "tools/external_tools/mcp/mcp_client*.py",
        "kind": "mcp_session",
        "id": "mcp_session",
    },
    {"glob": "prompt/*", "kind": "prompt"},
    {
        "glob": "tools/external_tools/ci_tools/generate/plugin",
        "kind": "ci",
        "id": "plugin_generate",
    },
)

PROJECT_TOPLEVEL = ("model", "context", "prompt", "tools", "kernel")

# Immediate children of these globs are plugin families (or collection
# containers that ancestor a family root). Data-only trees without Python
# (e.g. prompt/prompt_card) are ignored. Mirrors gen-tool-catalog's
# `packages/*/tool-*` disk scan.
FAMILY_SCAN_GLOBS: tuple[str, ...] = (
    "context/*",
    "context/context_compression/*",
    "model/*",
    "model/model_API/*",
    "model/model_API/model_paramaters/*",
    "prompt/*",
    "tools/external_tools/mcp/*",
    "tools/external_tools/ci_tools/generate/plugin",
)

SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    "pypyr-main",
}


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


def discover_families(
    repo: Path,
    rules: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build plugin families by globbing layout conventions on disk."""
    families: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for rule in rules if rules is not None else FAMILY_KIND_RULES:
        family_glob = str(rule["glob"]).replace("\\", "/")
        kind = str(rule["kind"])
        file_matches: list[Path] = []
        dir_matches: list[Path] = []
        wildcard = _glob_has_wild(family_glob)
        for path in _glob_repo(repo, family_glob):
            if _should_skip(repo, path):
                continue
            if path.is_dir() and (not wildcard or _dir_has_python(path)):
                dir_matches.append(path)
            elif path.is_file() and path.suffix == ".py":
                file_matches.append(path)
        if file_matches:
            root = file_matches[0].parent.relative_to(repo).as_posix()
            family_id = str(rule.get("id") or Path(root).name)
            key = (family_id, root, kind)
            if key not in seen:
                seen.add(key)
                families.append(
                    {
                        "id": family_id,
                        "root": root,
                        "kind": kind,
                        "glob": Path(family_glob).name,
                    }
                )
            continue
        for path in dir_matches:
            rel = path.relative_to(repo).as_posix()
            family_id = str(rule.get("id") or path.name)
            key = (family_id, rel, kind)
            if key in seen:
                continue
            seen.add(key)
            families.append({"id": family_id, "root": rel, "kind": kind})
    return families


def collect_on_disk_plugin_paths(
    repo: Path,
    scan_globs: tuple[str, ...] = FAMILY_SCAN_GLOBS,
) -> list[str]:
    """Return posix paths globbed from the tree that look like plugin families."""
    found: set[str] = set()
    for pattern in scan_globs:
        for path in _glob_repo(repo, pattern):
            if _should_skip(repo, path):
                continue
            rel = path.relative_to(repo).as_posix()
            if path.is_dir():
                if not _dir_has_python(path) and rel not in _exact_kind_roots():
                    continue
                found.add(rel)
            elif path.is_file() and path.suffix == ".py":
                found.add(rel)
    return sorted(found)


def assert_families_complete(
    context: dict[str, Any],
    families: Iterable[dict[str, Any]] | None = None,
    scan_globs: tuple[str, ...] = FAMILY_SCAN_GLOBS,
) -> dict[str, Any]:
    """Fail closed when a scanned plugin path is not classified by kind rules.

    Same guarantee as gen-tool-catalog ``assertManifestComplete``: a new
    sibling directory or MCP ``*_plugin.py`` cannot stay uncatalogued.
    """
    repo = Path(context["repo_root"])
    listed = [dict(family) for family in (families if families is not None else context["families"])]
    for rel in collect_on_disk_plugin_paths(repo, scan_globs):
        if _covered_by_inventory(rel, listed):
            continue
        context["violations"].append(
            {
                "rule": "inventory.unlisted",
                "path": rel,
                "detail": (
                    "on-disk plugin path is not classified by FAMILY_KIND_RULES; "
                    "add a kind glob or this path is not a plugin family"
                ),
                "severity": "error",
            }
        )
    return context


def _glob_has_wild(pattern: str) -> bool:
    return any(char in pattern for char in "*?[")


def _exact_kind_roots() -> set[str]:
    return {
        str(rule["glob"]).replace("\\", "/")
        for rule in FAMILY_KIND_RULES
        if not _glob_has_wild(str(rule["glob"]))
    }


def _should_skip(repo: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(repo).parts
    except ValueError:
        parts = path.parts
    return any(part in SKIP_DIR_NAMES or part.startswith(".") for part in parts)


def _glob_repo(repo: Path, pattern: str) -> list[Path]:
    if _glob_has_wild(pattern):
        return sorted(path for path in repo.glob(pattern))
    path = repo / pattern
    return [path] if path.exists() else []


def _dir_has_python(path: Path) -> bool:
    for child in path.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in child.parts):
            continue
        return True
    return False


def _covered_by_inventory(rel: str, families: Iterable[dict[str, Any]]) -> bool:
    rel = rel.replace("\\", "/")
    for family in families:
        root = str(family["root"]).replace("\\", "/")
        if rel == root:
            return True
        if root.startswith(rel + "/"):
            return True
        if rel.startswith(root + "/"):
            if _member_of_family(rel, family, root):
                return True
    return False


def _member_of_family(rel: str, family: dict[str, Any], root: str) -> bool:
    named = family.get("files")
    glob_pat = family.get("glob")
    inner = rel[len(root) + 1 :].replace("\\", "/")
    if named:
        return inner in named
    if glob_pat:
        return fnmatch.fnmatch(inner, glob_pat)
    return True


def load_check_plugin(path: Path) -> ModuleType:
    """Load a check plugin by file path. Mirrors pypyr step_cache loading."""
    spec = importlib.util.spec_from_file_location(
        f"plugin_generate_check_{path.stem}",
        path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load check plugin: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "run", None)):
        raise AttributeError(f"{path.name} is missing run(context)")
    return module


def discover_check_plugins(here: Path) -> list[Path]:
    """Deny list first, then allow list, then remaining Host-sibling checks."""

    def _checks(directory: Path) -> list[Path]:
        if not directory.is_dir():
            return []
        return sorted(path for path in directory.glob("*_check.py") if path.is_file())

    return [
        *_checks(here / "list" / "deny_list"),
        *_checks(here / "list" / "allow_list"),
        *_checks(here),
    ]


def render_report(context: dict[str, Any]) -> str:
    violations: list[dict[str, Any]] = context.get("violations") or []
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in violations:
        key = (
            str(item.get("rule", "")),
            str(item.get("path", "")),
            str(item.get("detail", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    violations = sorted(
        unique,
        key=lambda item: (
            item.get("rule", ""),
            item.get("path", ""),
            item.get("detail", ""),
        ),
    )
    context["violations"] = violations
    errors = [item for item in violations if item.get("severity") == "error"]
    warnings = [item for item in violations if item.get("severity") != "error"]
    families = context.get("families") or []
    lines = [
        "# Plugin conformance",
        "",
        "Generated by `tools/external_tools/ci_tools/generate/plugin_generate`.",
        "Independent check plugins do not import one another; this Host loads them.",
        "",
        f"- repo: `.`",
        f"- families: {len(families)}",
        f"- python files scanned: {context.get('file_count', 0)}",
        f"- errors: {len(errors)}",
        f"- warnings: {len(warnings)}",
        "",
        "## Families",
        "",
    ]
    for family in families:
        glob_s = family.get("glob") or ",".join(family.get("files") or []) or "*.py"
        lines.append(
            f"- `{family['id']}` kind=`{family['kind']}` root=`{family['root']}` files=`{glob_s}`"
        )
    lines.extend(["", "## Errors", ""])
    if not errors:
        lines.append("None.")
    else:
        for item in errors:
            lines.append(
                f"- `{item.get('rule')}` `{item.get('path')}`: {item.get('detail')}"
            )
    lines.extend(["", "## Warnings", ""])
    if not warnings:
        lines.append("None.")
    else:
        for item in warnings:
            lines.append(
                f"- `{item.get('rule')}` `{item.get('path')}`: {item.get('detail')}"
            )
    lines.append("")
    return "\n".join(lines)


def build_context(repo: Path) -> dict[str, Any]:
    return {
        "repo_root": str(repo),
        "families": discover_families(repo),
        "project_toplevel": list(PROJECT_TOPLEVEL),
        "allowlist": load_allowlist(repo),
        "violations": [],
        "file_count": 0,
        "facts": {},
    }


def run_checks(context: dict[str, Any], here: Path | None = None) -> dict[str, Any]:
    here = here or Path(__file__).resolve().parent
    assert_families_complete(context)
    for path in discover_check_plugins(here):
        module = load_check_plugin(path)
        returned = module.run(context)
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
        help="Fail when the committed report is stale or when errors exist.",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Repository root. Default: walk up from this file.",
    )
    args = parser.parse_args(argv)

    here = Path(__file__).resolve().parent
    repo = Path(args.root).resolve() if args.root else find_repo_root(here)
    context = run_checks(build_context(repo), here)
    report = render_report(context)
    report_path = here / REPORT_NAME
    errors = [
        item for item in context.get("violations") or []
        if item.get("severity") == "error"
    ]

    if args.check:
        committed = report_path.read_text(encoding="utf-8") if report_path.is_file() else None
        if committed != report:
            sys.stderr.write(
                f"plugin_generate: {REPORT_NAME} is stale. "
                "Run plugin_generate.py and commit the report.\n"
            )
            return 1
        if errors:
            sys.stderr.write(
                f"plugin_generate: {len(errors)} plugin convention error(s).\n"
            )
            sys.stderr.write(report)
            return 1
        sys.stdout.write(f"plugin_generate: {REPORT_NAME} is up to date.\n")
        return 0

    report_path.write_text(report, encoding="utf-8")
    sys.stdout.write(f"plugin_generate: wrote {report_path.name}\n")
    if errors:
        sys.stderr.write(
            f"plugin_generate: {len(errors)} plugin convention error(s).\n"
        )
        sys.stderr.write(report)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
