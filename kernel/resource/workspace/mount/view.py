"""Which paths one workspace lease can see."""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

_SECRET_NAMES = {"id_rsa", "id_ed25519", "credentials.json"}
_SECRET_PARTS = {".git", ".ssh", ".aws"}
_SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def private_temp(root: str, process_id: str) -> str:
    """A temp directory that belongs to one peer, under the shared project root."""
    base = Path(root).expanduser()
    name = process_id.strip()
    path = base / ".linope-tmp" / name if name else base / ".linope-tmp"
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
    """Resolve a path and keep it inside an allowed root.

    The caller opens the returned path. A symlink that lands outside the
    roots is rejected. Another process's private temp is rejected too.
    """
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
