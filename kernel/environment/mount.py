"""Which directories one process may see, and whether it may change them.

This used to be a leased workspace resource. It is part of the process room.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
DANGER_FULL_ACCESS = "danger-full-access"

MODES = (READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS)
CONFINED = (READ_ONLY, WORKSPACE_WRITE)

_SECRET_NAMES = {"id_rsa", "id_ed25519", "credentials.json"}
_SECRET_PARTS = {".git", ".ssh", ".aws"}
_SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def check_mode(mode: str) -> str:
    """Reject an unknown file mode."""
    if mode not in MODES:
        raise ValueError("文件模式只能是只读、工作区可写，或跳过包装")
    return mode


def writes(mode: str) -> bool:
    """Whether the workspace root itself may be changed."""
    return mode in {WORKSPACE_WRITE, DANGER_FULL_ACCESS}


def confines(mode: str) -> bool:
    """Whether an external command must be wrapped."""
    return mode in CONFINED


def project_identity(root: str) -> dict[str, str]:
    """The sandbox identity is the project root."""
    text = str(root or "").strip()
    if not text:
        raise ValueError("workspace root is required")
    return {"root": os.path.normpath(os.path.expanduser(text))}


def root_from(changes, fallback: str) -> str:
    """Read a project root from change clauses, otherwise use fallback."""
    for topic, raw in changes or ():
        if topic in {"workspace", "workspace_root", "cwd"} and str(raw).strip():
            return str(raw)
    return fallback


def private_temp(root: str, pid: int = 0) -> str:
    """A temp directory that belongs to one peer, under the shared project root."""
    base = Path(root).expanduser()
    path = base / ".linope-tmp" / str(pid) if pid > 0 else base / ".linope-tmp"
    return str(path)


def blocked(path: Path) -> bool:
    """Git metadata, secret files, and a home directory stay out of the view."""
    resolved = path.expanduser()
    if _is_home(resolved):
        return True
    if any(part in _SECRET_PARTS for part in resolved.parts):
        return True
    name = resolved.name
    if name == ".env" or name.startswith(".env."):
        return True
    if name in _SECRET_NAMES:
        return True
    folded = name.casefold()
    return any(folded.endswith(suffix) for suffix in _SECRET_SUFFIXES)


def inside(root: str, path: Path) -> bool:
    """Whether ``path`` is the root or a file inside it."""
    try:
        root_path = Path(root).expanduser().resolve()
    except OSError:
        root_path = Path(root).expanduser()
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        resolved = path.expanduser()
    return _contains(str(root_path), resolved)


def admit_path(
    candidate: Path,
    roots: Sequence[tuple[str, bool]],
    *,
    write: bool,
    own_temp: str = "",
) -> Path:
    """Resolve a path and keep it inside an allowed root."""
    requested = candidate.expanduser()
    try:
        resolved = requested.resolve()
    except OSError:
        resolved = requested
    if blocked(requested) or blocked(resolved) or _other_private_temp(resolved, own_temp):
        raise PermissionError("这个路径不在允许的地方")
    matches = [
        (root, writable)
        for root, writable in roots
        if _contains(root, resolved)
    ]
    if not matches:
        raise PermissionError("这个路径不在允许的地方")
    if write:
        deepest = max(matches, key=lambda item: (len(item[0]), 0 if item[1] else 1))
        if not deepest[1]:
            raise PermissionError("这里只能读，不能改")
    return resolved


def _other_private_temp(resolved: Path, own_temp: str) -> bool:
    if ".linope-tmp" not in resolved.parts:
        return False
    if own_temp and _contains(own_temp, resolved):
        return False
    return True


def _contains(root: str, path: Path) -> bool:
    try:
        root_path = Path(root).expanduser().resolve()
    except OSError:
        root_path = Path(root).expanduser()
    root_text = os.path.normcase(str(root_path))
    path_text = os.path.normcase(str(path))
    if path_text == root_text:
        return True
    prefix = root_text.rstrip("\\/") + os.sep
    return path_text.startswith(os.path.normcase(prefix))


def _is_home(path: Path) -> bool:
    home = Path.home()
    try:
        resolved = path.resolve()
        home_resolved = home.resolve()
    except OSError:
        resolved = path
        home_resolved = home
    return os.path.normcase(str(resolved)) == os.path.normcase(str(home_resolved))
