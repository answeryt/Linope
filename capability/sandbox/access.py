"""Runtime file-access policy owned by the capability sandbox.

The kernel may carry this policy, but it does not choose its roots.  The
policy is deliberately serializable so the same decision can be used by
direct file tools and external-command runners.
"""

from __future__ import annotations

import os
import string
from pathlib import Path
from typing import Any, Mapping

READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
DANGER_FULL_ACCESS = "danger-full-access"
SANDBOX_MODES = (READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS)

HOST_SCOPE = "host"
WORKSPACE_SCOPE = "workspace"

_SECRET_NAMES = {"id_rsa", "id_ed25519", "credentials.json"}
_SECRET_PARTS = {".git", ".ssh", ".aws"}
_SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def host_roots() -> tuple[str, ...]:
    """Return the filesystem roots visible to a host-scoped policy."""
    if os.name != "nt":
        return (os.path.abspath(os.sep),)
    drives: list[str] = []
    mask = 0
    try:
        import ctypes

        mask = int(ctypes.windll.kernel32.GetLogicalDrives())
    except (AttributeError, OSError, ValueError):
        mask = 0
    for index, letter in enumerate(string.ascii_uppercase):
        if mask & (1 << index):
            drives.append(f"{letter}:\\")
    if drives:
        return tuple(drives)
    return (Path.cwd().anchor or "C:\\",)


def resolve_policy(request: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Resolve one runtime policy without treating cwd as a security boundary."""
    raw = dict(request or {})
    mode = str(raw.get("mode") or WORKSPACE_WRITE)
    if mode not in SANDBOX_MODES:
        raise ValueError(f"unknown sandbox mode: {mode!r}")
    scope = str(raw.get("scope") or HOST_SCOPE)
    if scope not in {HOST_SCOPE, WORKSPACE_SCOPE}:
        raise ValueError(f"unknown sandbox scope: {scope!r}")
    cwd = _directory(raw.get("cwd") or os.getcwd())
    if scope == HOST_SCOPE:
        roots = host_roots()
        writable = roots if mode == WORKSPACE_WRITE else ()
    else:
        roots = (cwd,)
        writable = roots if mode == WORKSPACE_WRITE else ()
    return {
        "version": 1,
        "scope": scope,
        "mode": mode,
        "cwd": cwd,
        "roots": list(roots),
        "writable_roots": list(writable),
        "temp_root": os.path.abspath(os.getenv("TMPDIR") or os.getenv("TEMP") or os.getenv("TMP") or "/tmp"),
        "blocked_names": sorted(_SECRET_NAMES),
        "blocked_parts": sorted(_SECRET_PARTS),
        "blocked_suffixes": list(_SECRET_SUFFIXES),
    }


def policy_roots(policy: Mapping[str, Any]) -> tuple[str, ...]:
    """Return canonical roots from a resolved policy."""
    raw = policy.get("roots") or ()
    roots = tuple(_canonical(str(item)) for item in raw if str(item).strip())
    if roots:
        return roots
    return host_roots() if policy.get("scope") == HOST_SCOPE else (str(policy.get("cwd") or os.getcwd()),)


def writable_roots(policy: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the roots that may be modified under the policy."""
    mode = str(policy.get("mode") or "")
    if mode == DANGER_FULL_ACCESS:
        return policy_roots(policy)
    if mode != WORKSPACE_WRITE:
        return ()
    raw = policy.get("writable_roots") or policy_roots(policy)
    return tuple(_canonical(str(item)) for item in raw if str(item).strip())


def is_blocked(path: Path, policy: Mapping[str, Any] | None = None) -> bool:
    """Reject common credential and VCS locations unless explicitly bypassed."""
    if str((policy or {}).get("mode") or "") == DANGER_FULL_ACCESS:
        return False
    resolved = path.expanduser()
    if any(part in _SECRET_PARTS for part in resolved.parts):
        return True
    name = resolved.name
    if name == ".env" or name.startswith(".env."):
        return True
    if name in _SECRET_NAMES:
        return True
    folded = name.casefold()
    return any(folded.endswith(suffix) for suffix in _SECRET_SUFFIXES)


def resolve_path(
    path: str | Path,
    policy: Mapping[str, Any],
    *,
    base: str | Path | None = None,
    write: bool = False,
) -> Path:
    """Resolve a path and enforce the sandbox policy's roots."""
    raw = Path(path).expanduser()
    if not raw.is_absolute():
        raw = Path(base or policy.get("cwd") or os.getcwd()) / raw
    resolved = raw.resolve()
    if is_blocked(raw, policy) or is_blocked(resolved, policy):
        raise PermissionError("This path is blocked by the sandbox policy")
    if not any(_inside(root, resolved) for root in policy_roots(policy)):
        raise PermissionError("This path is outside the sandbox policy")
    if write and not any(_inside(root, resolved) for root in writable_roots(policy)):
        raise PermissionError("This path is read-only under the sandbox policy")
    return resolved


class SandboxFileAccess:
    """Small file API used by tools after the sandbox has chosen a policy."""

    def __init__(self, policy: Mapping[str, Any]) -> None:
        self.policy = dict(policy)

    def resolve(
        self,
        path: str,
        *,
        write: bool,
        base: str | Path | None = None,
    ) -> Path:
        return resolve_path(path, self.policy, base=base, write=write)

    def read_text(self, path: str, *, base: str | Path | None = None) -> str:
        return self.resolve(path, write=False, base=base).read_text(encoding="utf-8")

    def write_text(
        self,
        path: str,
        content: str,
        *,
        base: str | Path | None = None,
    ) -> Path:
        target = self.resolve(path, write=True, base=base)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target


def door_for(room: object | None, workspace: str | None = None) -> SandboxFileAccess:
    """Return the policy-backed file API for a capability room."""
    filesystem = getattr(room, "filesystem", None)
    policy = getattr(filesystem, "policy", None)
    if not isinstance(policy, dict) or not policy:
        policy = resolve_policy(
            {
                "scope": HOST_SCOPE,
                "mode": WORKSPACE_WRITE,
                "cwd": workspace or os.getcwd(),
            }
        )
    return SandboxFileAccess(policy)


def _directory(value: Any) -> str:
    path = Path(str(value or os.getcwd())).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"Sandbox cwd is not a directory: {path}")
    return str(path)


def _canonical(value: str) -> str:
    try:
        return str(Path(value).expanduser().resolve())
    except OSError:
        return os.path.normpath(os.path.expanduser(value))


def _inside(root: str, path: Path) -> bool:
    root_path = Path(root).expanduser()
    try:
        path.relative_to(root_path)
    except ValueError:
        return False
    return True
