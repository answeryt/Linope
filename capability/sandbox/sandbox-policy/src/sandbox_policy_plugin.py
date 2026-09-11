# -*- coding: utf-8 -*-
"""Resolve one per-call sandbox policy: approved mode > session > default.

Host injects canonical_path and effective_mode so this file never imports
roots or session-mode siblings. Runner choice is not here.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any


PLUGIN_NAME = "sandbox_policy"
PLUGIN_VERSION = "1.0"

READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
DANGER_FULL_ACCESS = "danger-full-access"

SANDBOX_MODES: tuple[str, ...] = (READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS)

CanonicalPath = Callable[[str], str]
EffectiveMode = Callable[[Any], str | None]


def require_sandbox_mode(mode: str) -> str:
    text = str(mode)
    if text not in SANDBOX_MODES:
        raise ValueError(f"unknown sandbox mode: {text!r}")
    return text


def render_policy_context(policy: Mapping[str, Any]) -> str:
    """Capability-neutral file policy text for the current request."""
    mode = str(policy.get("mode") or "")
    if mode == READ_ONLY:
        return (
            "Current Linope file policy: read-only. Any available operation "
            "enforced by the Linope file sandbox cannot modify files in the "
            "standing mode. Do not refuse a required modification from this "
            "policy alone: try an available tool normally and follow any denial "
            "and escalation guidance it returns."
        )
    if mode == WORKSPACE_WRITE:
        root = policy.get("workspace_root", policy.get("workspaceRoot"))
        return (
            "Current Linope file policy: workspace-write. Any available "
            "operation enforced by the Linope file sandbox may modify files "
            f"under the session workspace: {root!r}. Some platform temporary "
            "areas may also be writable."
        )
    if mode == DANGER_FULL_ACCESS:
        return (
            "Current Linope file policy: danger-full-access. The Linope "
            "file sandbox does not restrict file modifications by available "
            "operations."
        )
    raise ValueError(f"unreachable sandbox mode: {mode}")


class SandboxPolicy:
    """Deployment default plus per-call resolve. Executors stay session-free."""

    def __init__(
        self,
        *,
        canonical_path: CanonicalPath,
        effective_mode: EffectiveMode,
        mode: str = READ_ONLY,
        workspace_root: str | None = None,
    ) -> None:
        if canonical_path is None or effective_mode is None:
            raise TypeError("canonical_path and effective_mode are required")
        self.canonical_path = canonical_path
        self.effective_mode = effective_mode
        self.default_mode = require_sandbox_mode(mode)
        self.workspace_root = self._resolve_root(workspace_root or os.getcwd())

    def resolve(self, request: Mapping[str, Any] | None = None) -> dict[str, Any]:
        request = request or {}
        session = request.get("session")
        approved = request.get("mode")
        mode = (
            require_sandbox_mode(str(approved))
            if approved is not None
            else self.override_of(session) or self.default_mode
        )
        cwd = _session_cwd(session)
        policy: dict[str, Any] = {
            "mode": mode,
            "workspace_root": self._resolve_root(cwd or self.workspace_root),
        }
        session_id = _session_id(session)
        if session_id is not None:
            policy["session_id"] = session_id
        return policy

    def override_of(self, session: Any) -> str | None:
        if session is None:
            return None
        events = session.get("events") if isinstance(session, Mapping) else getattr(session, "events", None)
        if events is None:
            return None
        return self.effective_mode(events)

    def render(self, request: Mapping[str, Any] | None = None) -> str:
        request = request or {}
        if request.get("session") is None:
            return ""
        return render_policy_context(self.resolve(request))

    def _resolve_root(self, path: str) -> str:
        return os.path.abspath(self.canonical_path(path))


def build_policy(
    *,
    canonical_path: CanonicalPath,
    effective_mode: EffectiveMode,
    mode: str = READ_ONLY,
    workspace_root: str | None = None,
) -> SandboxPolicy:
    """Host entry: inject path identity and the session-mode fold."""
    return SandboxPolicy(
        canonical_path=canonical_path,
        effective_mode=effective_mode,
        mode=mode,
        workspace_root=workspace_root,
    )


def _session_cwd(session: Any) -> str | None:
    if session is None:
        return None
    header = session.get("header") if isinstance(session, Mapping) else getattr(session, "header", None)
    if isinstance(header, Mapping):
        cwd = header.get("cwd")
        return None if cwd is None else str(cwd)
    if header is not None:
        cwd = getattr(header, "cwd", None)
        if cwd is not None:
            return str(cwd)
    if isinstance(session, Mapping):
        cwd = session.get("cwd")
        return None if cwd is None else str(cwd)
    cwd = getattr(session, "cwd", None)
    return None if cwd is None else str(cwd)


def _session_id(session: Any) -> str | None:
    if session is None:
        return None
    if isinstance(session, Mapping):
        value = session.get("id") or session.get("session_id")
        return None if value is None else str(value)
    value = getattr(session, "id", None) or getattr(session, "session_id", None)
    return None if value is None else str(value)
