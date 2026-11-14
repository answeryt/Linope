# -*- coding: utf-8 -*-
"""bwrap / Landlock / Seatbelt profile argv. Host injects writable_roots."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


PLUGIN_NAME = "sandbox_profiles"
PLUGIN_VERSION = "1.0"

WORKSPACE_WRITE = "workspace-write"


def bwrap_profile_args(policy: Mapping[str, Any]) -> list[str]:
    scope = str(policy.get("scope") or "")
    writable = str(policy.get("mode") or "") == WORKSPACE_WRITE
    if scope == "host" and writable:
        args = ["--bind", "/", "/"]
    else:
        args = ["--ro-bind", "/", "/"]
    args.extend(["--dev", "/dev", "--proc", "/proc", "--die-with-parent"])
    if str(policy.get("mode") or "") == WORKSPACE_WRITE:
        roots = list(policy.get("writable_roots") or ())
        if not roots:
            roots = [str(policy.get("workspace_root") or policy.get("workspaceRoot") or "")]
        if scope != "host":
            args.extend(["--tmpfs", "/tmp"])
            args.extend(item for root in roots for item in ("--bind", str(root), str(root)))
    return args


def landlock_profile_args(policy: Mapping[str, Any]) -> list[str]:
    """landlock-run style grants. Missing binary stays fail-closed at confine."""
    args = ["--ro", "/"]
    read_write = ["/dev/null"]
    if str(policy.get("mode") or "") == WORKSPACE_WRITE:
        roots = list(policy.get("writable_roots") or ())
        if roots:
            read_write.extend(str(root) for root in roots)
        else:
            read_write.extend(["/tmp", str(policy.get("workspace_root") or policy.get("workspaceRoot") or "")])
    for path in read_write:
        args.extend(["--rw", path])
    return args


def seatbelt_profile_args(
    policy: Mapping[str, Any],
    *,
    writable_roots: Callable[[Mapping[str, Any]], list[str]],
) -> list[str]:
    forms = [
        "(version 1)",
        "(allow default)",
        "(deny file-write*)",
        f'(allow file-write* (literal {_sbpl("/dev/null")}))',
    ]
    roots = writable_roots(policy)
    if roots:
        grants = " ".join(f"(subpath {_sbpl(root)})" for root in roots)
        forms.append(f"(allow file-write* {grants})")
    return ["-p", " ".join(forms)]


def _sbpl(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'
