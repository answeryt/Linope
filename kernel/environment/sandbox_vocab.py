"""Sandbox mode and writable-root rules, answered by the sandbox program.

This module does not define a second mode list or load a plugin file itself.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


_VOCAB: dict[str, Any] | None = None
_MODES: Any = None
_ROOTS: Any = None


def _gate(payload: dict[str, Any]) -> Any:
    env = os.environ.copy()
    root = str(Path(__file__).resolve().parents[2])
    current = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root if not current else root + os.pathsep + current
    completed = subprocess.run(
        [sys.executable, "-m", "capability.sandbox.gate"],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "sandbox gate failed"
        raise RuntimeError(detail)
    text = completed.stdout.strip()
    if not text:
        return None
    return json.loads(text)


def register_vocabulary(modes: Any, roots: Any) -> None:
    """Remember the sandbox modules a capability program already loaded."""
    global _MODES, _ROOTS, _VOCAB
    _MODES = modes
    _ROOTS = roots
    _VOCAB = {
        "read_only": modes.READ_ONLY,
        "workspace_write": modes.WORKSPACE_WRITE,
        "danger_full_access": modes.DANGER_FULL_ACCESS,
        "modes": list(modes.SANDBOX_MODES),
        "confined": list(getattr(modes, "CONFINED_MODES", ()) or (modes.READ_ONLY, modes.WORKSPACE_WRITE)),
    }


def vocabulary() -> dict[str, Any]:
    """The mode names the sandbox program publishes."""
    global _VOCAB
    if _VOCAB is None:
        found = _gate({"op": "vocabulary"})
        if not isinstance(found, dict):
            raise RuntimeError("sandbox gate did not name its modes")
        _VOCAB = found
    return _VOCAB


READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
DANGER_FULL_ACCESS = "danger-full-access"


def _modes() -> tuple[str, ...]:
    return tuple(str(item) for item in vocabulary().get("modes") or ())


def _confined() -> tuple[str, ...]:
    return tuple(str(item) for item in vocabulary().get("confined") or ())


def modes() -> tuple[str, ...]:
    return _modes()


def check_mode(mode: str) -> str:
    """Reject a mode the sandbox vocabulary does not define."""
    text = str(mode)
    known = _modes() or (READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS)
    if text not in known:
        raise ValueError("File mode must be read-only, workspace-write, or skip wrapping")
    return text


def confines(mode: str) -> bool:
    """Whether an external command must be wrapped."""
    return check_mode(mode) in (_confined() or (READ_ONLY, WORKSPACE_WRITE))


def writes(mode: str) -> bool:
    """Whether the mode may change files, derived from the sandbox rules."""
    text = check_mode(mode)
    if not confines(text):
        return True
    return bool(writable_roots({"mode": text, "workspace_root": "."}))


def writable_roots(policy: dict[str, Any]) -> list[str]:
    """The sandbox allow-list for one file-effect policy."""
    if _ROOTS is not None:
        return list(_ROOTS.writable_roots(policy))
    found = _gate({"op": "writable-roots", "policy": policy})
    return list(found or [])


def resolve_policy(request: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ask capability/sandbox for one runtime access policy."""
    found = _gate(
        {
            "op": "resolve-policy",
            "request": dict(request or {}),
        }
    )
    if not isinstance(found, dict):
        raise RuntimeError("sandbox gate did not return an access policy")
    return dict(found)


def canonical_path(path: str) -> str:
    """The path identity the sandbox uses when comparing roots."""
    if _ROOTS is not None:
        return str(_ROOTS.canonical_path(path))
    return str(_gate({"op": "canonical-path", "path": path}) or "")


def narrower(left: str, right: str) -> str:
    """The stricter of two sandbox modes. Order comes from the sandbox mode list."""
    first = check_mode(left)
    second = check_mode(right)
    order = _modes() or (READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS)
    if order.index(first) <= order.index(second):
        return first
    return second


# Callers import MODES as a tuple. Fill it on first use via a tuple subclass that reads late.
class _ModeTuple(tuple):
    def __new__(cls) -> "_ModeTuple":
        return tuple.__new__(cls, ())

    def __iter__(self):
        return iter(_modes())

    def __contains__(self, item: object) -> bool:
        return item in _modes()

    def __len__(self) -> int:
        return len(_modes())

    def __getitem__(self, item):
        return _modes()[item]

    def index(self, value: Any, *args: Any) -> int:
        return _modes().index(value, *args)


MODES = _ModeTuple()
CONFINED = _ModeTuple()
