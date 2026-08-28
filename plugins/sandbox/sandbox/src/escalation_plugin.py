# -*- coding: utf-8 -*-
"""Shared sandbox escalation ladder, markers, and fail-closed approval.

Tool families hand in a structural approver; this file never imports approval
or agent plugins. Mode names are local so this file does not import the
vocabulary sibling.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PLUGIN_NAME = "sandbox_escalation"
PLUGIN_VERSION = "1.0"

READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
DANGER_FULL_ACCESS = "danger-full-access"

WIDER_MODES: dict[str, tuple[str, ...]] = {
    READ_ONLY: (WORKSPACE_WRITE, DANGER_FULL_ACCESS),
    WORKSPACE_WRITE: (DANGER_FULL_ACCESS,),
}

ESCALATION_TARGETS: tuple[str, ...] = (WORKSPACE_WRITE, DANGER_FULL_ACCESS)

ALLOWED_ONCE = "allowed-once"
REJECTED = "rejected"
CANCELLED = "cancelled"
UNAVAILABLE = "unavailable"
OUTCOMES = frozenset({ALLOWED_ONCE, REJECTED, CANCELLED, UNAVAILABLE})


def validate_escalation_args(
    sandbox_permissions: str | None,
    justification: str | None,
) -> None:
    """sandbox_permissions and justification travel together."""
    if sandbox_permissions is not None and justification is None:
        raise ValueError("invalid escalation: sandbox_permissions requires a justification")
    if justification is not None and sandbox_permissions is None:
        raise ValueError(
            "invalid escalation: justification is only valid together with sandbox_permissions"
        )
    if justification is not None and justification.strip() == "":
        raise ValueError("invalid justification: expected a non-empty sentence")


def sandbox_denial_marker(mode: str) -> str:
    return f"[sandbox: file access denied under {mode} mode]"


def escalation_hint_marker(subject: str) -> str:
    return (
        f"[sandbox: escalation available — retry this exact {subject} once with "
        "sandbox_permissions (the narrowest wider mode that suffices) + "
        "justification; the approval prompt asks the user]"
    )


def approve_escalation(
    request: Mapping[str, Any],
    approval: Mapping[str, Any],
) -> str:
    """Grant a strictly wider mode for this call, or raise before anything runs."""
    mode = _text(request, "requested_mode", "requestedMode")
    effective = _text(request, "effective_mode", "effectiveMode")
    justification = _text(request, "justification")
    subject = _text(request, "subject") or "command"
    if mode not in WIDER_MODES.get(effective, ()):
        raise ValueError(
            f'sandbox escalation to "{mode}" is not strictly wider than this '
            f'call\'s current "{effective}" mode'
        )
    approver = approval.get("approver")
    if approver is None:
        raise ValueError(
            f'sandbox escalation to "{mode}" requires approval, but no '
            "approval service is composed"
        )
    agent = approval.get("agent")
    if agent is None:
        raise ValueError(
            f'sandbox escalation to "{mode}" requires approval, but the call '
            "has no agent to route it through"
        )
    payload: dict[str, Any] = {
        "agent": agent,
        "tool_name": approval.get("tool_name", approval.get("toolName")),
        "call_id": approval.get("call_id", approval.get("callId")),
        "reason": f"escalate sandbox to {mode}: {justification}",
    }
    signal = approval.get("signal")
    if signal is not None:
        payload["signal"] = signal
    outcome = str(_ask(approver, payload))
    if outcome == ALLOWED_ONCE:
        return mode
    if outcome == REJECTED:
        raise ValueError(
            f'the user rejected escalating this {subject} to "{mode}"'
        )
    if outcome == CANCELLED:
        raise ValueError(f'approval for escalating to "{mode}" was cancelled')
    if outcome == UNAVAILABLE:
        raise ValueError(
            f'sandbox escalation to "{mode}" requires approval, but no '
            "approval channel is available"
        )
    raise ValueError(f"unreachable escalation outcome: {outcome}")


def _text(record: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = record.get(name)
        if value is not None:
            return str(value)
    return ""


def _ask(approver: Any, payload: Mapping[str, Any]) -> Any:
    request = getattr(approver, "request", None)
    if callable(request):
        return request(payload)
    if callable(approver):
        return approver(payload)
    raise TypeError("approver must provide request")
