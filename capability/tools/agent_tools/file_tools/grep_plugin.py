# -*- coding: utf-8 -*-
"""Search file contents with a regular expression."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional


PLUGIN_NAME = "grep"
PLUGIN_VERSION = "1.0"

GREP_MAX_MATCHES = 250
VCS_EXCLUDES = {".git", ".hg", ".svn"}

GREP_SCHEMA: dict[str, Any] = {
    "name": "grep",
    "description": (
        "Search file contents with a regular expression. Returns matching "
        "lines with line numbers, grouped by file. Returns the first 250 "
        "matches inline. Use read on a matched file for surrounding context."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regular expression to search for (ripgrep syntax when rg is available).",
            },
            "path": {
                "type": "string",
                "description": (
                    "File or directory to search. Defaults to the session "
                    "workspace; a relative path resolves against it."
                ),
            },
            "include": {
                "type": "string",
                "description": 'One glob filter for which files to search (e.g. "*.ts").',
            },
        },
        "required": ["pattern"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [GREP_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('grep', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "grep":
        return _error(f"unknown tool: {name}")
    return grep_files(
        str(arguments.get("pattern") or ""),
        arguments.get("path"),
        arguments.get("include"),
        **kwargs,
    )


def grep_files(
    pattern: str,
    path: Optional[str] = None,
    include: Optional[str] = None,
    workspace: Optional[str] = None,
) -> str:
    if not pattern.strip():
        return _error("invalid pattern: expected a non-empty string")
    root = Path(workspace or os.getenv("TERMINAL_CWD") or os.getcwd())
    if path:
        candidate = Path(path)
        root = candidate if candidate.is_absolute() else root / candidate
    root = root.resolve()
    rg = shutil.which("rg")
    if rg is not None:
        argv = [rg, "--json", "--max-count", str(GREP_MAX_MATCHES), "-e", pattern]
        if include:
            argv.extend(["--glob", include])
        argv.append(str(root))
        try:
            completed = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return _error(str(exc))
        groups: dict[str, list[dict[str, Any]]] = {}
        for line in completed.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") != "match":
                continue
            data = event.get("data") or {}
            rel = str((data.get("path") or {}).get("text") or "")
            if rel.startswith(str(root)):
                rel = Path(rel).relative_to(root).as_posix()
            text = ((data.get("lines") or {}).get("text") or "").rstrip("\n")
            groups.setdefault(rel, []).append(
                {"line": int((data.get("line_number") or 0)), "text": text}
            )
            if sum(len(items) for items in groups.values()) >= GREP_MAX_MATCHES:
                break
        total = sum(len(items) for items in groups.values())
        return json.dumps(
            {"success": True, "path": str(root), "matches": groups, "count": total, "truncated": total >= GREP_MAX_MATCHES},
            ensure_ascii=False,
        )
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return _error(f"invalid regular expression: {exc}")
    include_re = None
    if include:
        escaped = re.escape(include).replace(r"\*", ".*").replace(r"\?", ".")
        include_re = re.compile(f"^{escaped}$")
    groups = {}
    files = [root] if root.is_file() else root.rglob("*")
    for candidate in files:
        if not candidate.is_file() or any(part in VCS_EXCLUDES for part in candidate.parts):
            continue
        rel = candidate.relative_to(root if root.is_dir() else root.parent).as_posix()
        if include_re is not None and include_re.search(candidate.name) is None:
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            if regex.search(line) is None:
                continue
            groups.setdefault(rel, []).append({"line": index, "text": line})
            if sum(len(items) for items in groups.values()) >= GREP_MAX_MATCHES:
                total = sum(len(items) for items in groups.values())
                return json.dumps(
                    {"success": True, "path": str(root), "matches": groups, "count": total, "truncated": True},
                    ensure_ascii=False,
                )
    total = sum(len(items) for items in groups.values())
    return json.dumps(
        {"success": True, "path": str(root), "matches": groups, "count": total, "truncated": False},
        ensure_ascii=False,
    )


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)

def capability_profile(capability_id, changes):
    """Tell the process this tool needs a tool resource."""
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
        ),
    )

