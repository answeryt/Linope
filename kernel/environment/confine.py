"""Hand a workspace root and file mode to the platform wrapper."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kernel.environment.sandbox_vocab import confines


_ROOT = Path(__file__).resolve().parents[2]
_SANDBOX = _ROOT / "capability" / "sandbox"
_CACHE: Any = None

Isolator = Callable[[tuple[str, ...], str, str], dict[str, Any]]


def host_isolator(mode: str) -> Isolator:
    """Wrap a confined command. An unconfined mode keeps the original argv."""

    def isolate(argv: tuple[str, ...], directory: str, workspace_root: str) -> dict[str, Any]:
        del directory
        if not confines(mode):
            return {
                "argv": list(argv),
                "enforcement": None,
                "denial_signatures": [],
                "runner_failure_rules": [],
            }
        result = _sandbox().confine(
            list(argv),
            {"mode": mode, "workspace_root": workspace_root},
        )
        return dict(result)

    return isolate


def runner_failure_detail(
    exit_code: int | None,
    stderr: str,
    rules: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> str | None:
    """The fatal runner line, when the sandbox runner failed before the command."""
    if not exit_code or not rules:
        return None
    for rule in rules:
        allowed = rule.get("allowed_exit_codes") or rule.get("allowedExitCodes")
        if allowed and int(exit_code) not in {int(item) for item in allowed}:
            continue
        informational = {
            str(line).strip().casefold()
            for line in (rule.get("informational_lines") or rule.get("informationalLines") or ())
        }
        signatures = [
            str(item).casefold()
            for item in (rule.get("fatal_signatures") or rule.get("fatalSignatures") or ())
            if str(item)
        ]
        for raw in stderr.splitlines():
            line = raw.strip()
            if line.casefold() in informational:
                continue
            folded = line.casefold()
            if any(signature in folded for signature in signatures):
                return line
    return None


def denial_in_output(exit_code: int | None, stderr: str, signatures: tuple[str, ...] | list[str]) -> bool:
    """Whether a failed command was denied by the selected sandbox dialect."""
    if not exit_code or not signatures:
        return False
    folded = stderr.casefold()
    return any(str(signature).casefold() in folded for signature in signatures)


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
        raise RuntimeError(f"Cannot open the sandbox wrapper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
