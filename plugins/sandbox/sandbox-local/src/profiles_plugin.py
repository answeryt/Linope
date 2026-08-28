# -*- coding: utf-8 -*-
"""bwrap / Landlock / Seatbelt profile argv. Host injects writable_roots."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


PLUGIN_NAME = "sandbox_profiles"
PLUGIN_VERSION = "1.0"

WORKSPACE_WRITE = "workspace-write"


def bwrap_profile_args(policy: Mapping[str, Any]) -> list[str]:
    args = ["--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--die-with-parent"]
    if str(policy.get("mode") or "") == WORKSPACE_WRITE:
        root = str(policy.get("workspace_root") or policy.get("workspaceRoot") or "")
        args.extend(["--tmpfs", "/tmp", "--bind", root, root])
    return args


def landlock_profile_args(policy: Mapping[str, Any]) -> list[str]:
    """landlock-run style grants. Missing binary stays fail-closed at confine."""
    args = ["--ro", "/"]
    read_write = ["/dev/null"]
    if str(policy.get("mode") or "") == WORKSPACE_WRITE:
        root = str(policy.get("workspace_root") or policy.get("workspaceRoot") or "")
        read_write.extend(["/tmp", root])
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
