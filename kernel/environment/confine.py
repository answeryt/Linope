"""Hand a workspace root and file mode to the platform wrapper."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kernel.environment.sandbox_vocab import _gate, confines


_ISOLATOR: Any = None

Isolator = Callable[[tuple[str, ...], str, str], dict[str, Any]]


def register_isolator(isolate: Any) -> None:
    """Remember the command wrapper a capability program already built."""
    global _ISOLATOR
    _ISOLATOR = isolate


def host_isolator(mode: str, policy: dict[str, Any] | None = None) -> Isolator:
    """Wrap a confined command. An unconfined mode keeps the original argv."""

    def isolate(argv: tuple[str, ...], directory: str, workspace_root: str) -> dict[str, Any]:
        if not confines(mode):
            return {
                "argv": list(argv),
                "enforcement": None,
                "denial_signatures": [],
                "runner_failure_rules": [],
            }
        if _ISOLATOR is not None:
            return dict(_ISOLATOR(list(argv), directory, workspace_root, mode))
        request: dict[str, Any] = {
            "op": "confine",
            "argv": list(argv),
            "mode": mode,
            "workspace_root": workspace_root,
        }
        if policy:
            request.update(
                {
                    "scope": policy.get("scope", ""),
                    "roots": list(policy.get("roots") or ()),
                    "writable_roots": list(policy.get("writable_roots") or ()),
                }
            )
        result = _gate(request)
        return dict(result or {})

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

