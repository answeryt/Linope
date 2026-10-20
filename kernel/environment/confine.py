"""Hand a workspace root and file mode to the platform wrapper."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kernel.environment.mount import DANGER_FULL_ACCESS


_ROOT = Path(__file__).resolve().parents[2]
_SANDBOX = _ROOT / "capability" / "sandbox"
_CACHE: Any = None

Isolator = Callable[[tuple[str, ...], str], tuple[str, ...]]


def host_isolator(mode: str) -> Isolator:
    """Wrap a confined command. ``danger-full-access`` keeps the original argv."""

    def isolate(argv: tuple[str, ...], directory: str) -> tuple[str, ...]:
        if mode == DANGER_FULL_ACCESS:
            return tuple(argv)
        result = _sandbox().confine(
            list(argv),
            {"mode": mode, "workspace_root": directory},
        )
        return tuple(str(part) for part in result["argv"])

    return isolate


def _sandbox() -> Any:
    global _CACHE
    if _CACHE is None:
        profiles = _load(
            "linope_sandbox_profiles",
            _SANDBOX / "sandbox-local" / "src" / "profiles_plugin.py",
        )
        roots = _load(
            "linope_sandbox_roots",
            _SANDBOX / "sandbox" / "src" / "roots_plugin.py",
        )
        local = _load(
            "linope_sandbox_local",
            _SANDBOX / "sandbox-local" / "src" / "sandbox_local_plugin.py",
        )
        _CACHE = local.build_local_sandbox(
            bwrap_profile_args=profiles.bwrap_profile_args,
            landlock_profile_args=profiles.landlock_profile_args,
            seatbelt_profile_args=profiles.seatbelt_profile_args,
            writable_roots=roots.writable_roots,
            platform=sys.platform,
        )
    return _CACHE


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"打不开沙箱包装器: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
