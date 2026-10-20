# -*- coding: utf-8 -*-
"""Same-world process-sandbox vocabulary and confine contract.

Owns the three file-effect modes, the per-call policy shape, the fail-closed
SANDBOX_UNAVAILABLE error, and helpers that build a confined argv result.
Backends live in other families and are injected by Host. This file never
imports sibling plugins or a platform runner.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


PLUGIN_NAME = "sandbox_provider"
PLUGIN_VERSION = "1.0"

READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
DANGER_FULL_ACCESS = "danger-full-access"

SANDBOX_MODES = (READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS)
CONFINED_MODES = (READ_ONLY, WORKSPACE_WRITE)

ENFORCEMENT_FULL = "full"
ENFORCEMENT_PARTIAL = "partial"

SANDBOX_UNAVAILABLE = "SANDBOX_UNAVAILABLE"

_UNAVAILABLE = (
    'sandbox mode "{mode}" is requested but no sandbox backend is usable on this host; '
    "refusing to run the command unconfined. Install bubblewrap or run a Landlock-enforcing "
    "kernel (Linux), ensure sandbox-exec is usable (macOS), or ensure the ACL "
    "restricted-token runner can start (Windows) — otherwise switch the consumer to "
    "danger-full-access."
)


class SandboxUnavailableError(Exception):
    """Requested a confined mode but no backend can enforce it."""

    def __init__(self, mode: str, detail: str | None = None) -> None:
        message = _UNAVAILABLE.format(mode=mode)
        if detail is not None:
            message = f"{message} Runner failure: {detail}"
        super().__init__(message)
        self.name = "SandboxUnavailableError"
        self.code = SANDBOX_UNAVAILABLE
        self.mode = mode


def is_sandbox_mode(mode: str) -> bool:
    return mode in SANDBOX_MODES


def is_confined_mode(mode: str) -> bool:
    return mode in CONFINED_MODES


def requires_confine(mode: str) -> bool:
    """danger-full-access skips confine and spawns the original argv."""
    return str(mode) != DANGER_FULL_ACCESS


def require_confined_mode(mode: str) -> str:
    text = str(mode)
    if text not in CONFINED_MODES:
        raise ValueError(
            f'sandbox confine rejects "{text}"; use read-only or workspace-write, '
            "or skip confine under danger-full-access"
        )
    return text


def load(kind, body, call_params=None):
    """Load a sandbox execution policy. The mode stays in this package."""
    if kind != "sandbox":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("sandbox 的内容必须是映射")
    extras = dict(call_params or {})
    return execution_policy(
        str(body.get("mode") or ""),
        str(body.get("workspace_root") or extras.get("workspace_root") or ""),
        body.get("session_id"),
    )


def capability_profile(capability_id, changes):
    import os

    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.environment.mount import project_identity, root_from
    from kernel.resource.definition import ResourceKind

    root = root_from(changes, os.getcwd())
    mode = "workspace-write"
    for topic, raw in changes or ():
        if topic == "mode" and str(raw).strip():
            mode = str(raw)
    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(
                kind=ResourceKind.SANDBOX,
                identity=project_identity(root),
                call_params={"mode": mode},
            ),
        ),
    )


def execution_policy(
    mode: str,
    workspace_root: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Per-call policy. Root is carried even when the mode does not write."""
    if mode not in SANDBOX_MODES:
        raise ValueError(f"unknown sandbox mode: {mode!r}")
    policy: dict[str, Any] = {
        "mode": mode,
        "workspace_root": workspace_root,
    }
    if session_id is not None:
        policy["session_id"] = session_id
    return policy


def confined_argv(
    argv: Sequence[str],
    *,
    enforcement: str,
    denial_signatures: Sequence[str],
    runner_failure_rules: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Result callers spawn instead of their own argv."""
    if enforcement not in {ENFORCEMENT_FULL, ENFORCEMENT_PARTIAL}:
        raise ValueError(f"unknown sandbox enforcement: {enforcement!r}")
    return {
        "argv": list(argv),
        "enforcement": enforcement,
        "denial_signatures": list(denial_signatures),
        "runner_failure_rules": [dict(rule) for rule in runner_failure_rules],
    }


def sandbox_unavailable(mode: str, detail: str | None = None) -> None:
    """Fail closed. Never used to pass the original argv through."""
    raise SandboxUnavailableError(require_confined_mode(mode), detail)
