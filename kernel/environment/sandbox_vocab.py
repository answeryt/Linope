"""Sandbox mode and writable-root rules, loaded from capability/sandbox.

This module is an adapter. It does not define a second mode list or a second
writable-root rule.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[2]
_SANDBOX = _ROOT / "capability" / "sandbox" / "sandbox" / "src"
_CACHE: tuple[Any, Any] | None = None


def _load(name: str, filename: str) -> Any:
    path = _SANDBOX / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot open the sandbox vocabulary: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def vocabulary() -> tuple[Any, Any]:
    """The sandbox mode module and the writable-root module."""
    global _CACHE
    if _CACHE is None:
        _CACHE = (
            _load("linope_sandbox_vocab", "sandbox_plugin.py"),
            _load("linope_sandbox_roots_vocab", "roots_plugin.py"),
        )
    return _CACHE


def _modes() -> Any:
    return vocabulary()[0]


def _roots() -> Any:
    return vocabulary()[1]


READ_ONLY = _modes().READ_ONLY
WORKSPACE_WRITE = _modes().WORKSPACE_WRITE
DANGER_FULL_ACCESS = _modes().DANGER_FULL_ACCESS
MODES = _modes().SANDBOX_MODES
CONFINED = _modes().CONFINED_MODES


def check_mode(mode: str) -> str:
    """Reject a mode the sandbox vocabulary does not define."""
    text = str(mode)
    if text not in MODES:
        raise ValueError("File mode must be read-only, workspace-write, or skip wrapping")
    return text


def confines(mode: str) -> bool:
    """Whether an external command must be wrapped. The sandbox plugin decides."""
    return bool(_modes().requires_confine(check_mode(mode)))


def writes(mode: str) -> bool:
    """Whether the mode may change files, derived from the sandbox rules."""
    text = check_mode(mode)
    if not confines(text):
        return True
    return bool(writable_roots({"mode": text, "workspace_root": os.devnull or "."}))


def writable_roots(policy: dict[str, Any]) -> list[str]:
    """The sandbox allow-list for one file-effect policy."""
    return list(_roots().writable_roots(policy))


def canonical_path(path: str) -> str:
    """The path identity the sandbox uses when comparing roots."""
    return str(_roots().canonical_path(path))


def narrower(left: str, right: str) -> str:
    """The stricter of two sandbox modes. Order comes from SANDBOX_MODES."""
    first = check_mode(left)
    second = check_mode(right)
    if MODES.index(first) <= MODES.index(second):
        return first
    return second
