# -*- coding: utf-8 -*-
"""Pin the escalation ladder, argument pairing, markers, and fail-closed grant."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _load():
    path = Path(__file__).resolve().parents[1] / "src" / "escalation_plugin.py"
    spec = importlib.util.spec_from_file_location("sandbox_escalation", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Approver:
    def __init__(self, outcome: str, sink: list[Any] | None = None) -> None:
        self.outcome = outcome
        self.sink = sink

    def request(self, payload: Any) -> str:
        if self.sink is not None:
            self.sink.append(payload)
        return self.outcome


def test_wider_ladder() -> None:
    esc = _load()
    assert esc.WIDER_MODES["read-only"] == ("workspace-write", "danger-full-access")
    assert esc.WIDER_MODES["workspace-write"] == ("danger-full-access",)
    assert "danger-full-access" not in esc.WIDER_MODES
    assert esc.ESCALATION_TARGETS == ("workspace-write", "danger-full-access")


def test_validate_escalation_args() -> None:
    esc = _load()
    esc.validate_escalation_args(None, None)
    esc.validate_escalation_args("workspace-write", "because the workspace needs it")
    try:
        esc.validate_escalation_args("workspace-write", None)
    except ValueError as exc:
        assert "requires a justification" in str(exc)
    else:
        raise AssertionError("expected pairing error")
    try:
        esc.validate_escalation_args(None, "orphan reason")
    except ValueError as exc:
        assert "only valid together with sandbox_permissions" in str(exc)
    else:
        raise AssertionError("expected pairing error")
    try:
        esc.validate_escalation_args("workspace-write", "   ")
    except ValueError as exc:
        assert "non-empty sentence" in str(exc)
    else:
        raise AssertionError("expected blank justification error")


def test_markers() -> None:
    esc = _load()
    assert esc.sandbox_denial_marker("read-only") == (
        "[sandbox: file access denied under read-only mode]"
    )
    assert esc.sandbox_denial_marker("workspace-write") == (
        "[sandbox: file access denied under workspace-write mode]"
    )
    assert "retry this exact command once with sandbox_permissions" in (
        esc.escalation_hint_marker("command")
    )
    assert "retry this exact operation once with sandbox_permissions" in (
        esc.escalation_hint_marker("operation")
    )


def _request(**over: Any) -> dict[str, Any]:
    payload = {
        "requested_mode": "workspace-write",
        "justification": "the user asked to write in the workspace",
        "effective_mode": "read-only",
        "subject": "command",
    }
    payload.update(over)
    return payload


def _approval(esc: Any, **over: Any) -> dict[str, Any]:
    payload = {
        "approver": _Approver("allowed-once"),
        "agent": {},
        "call_id": "call-1",
        "tool_name": "bash",
    }
    payload.update(over)
    return payload


def test_grant_asks_with_audit_reason() -> None:
    esc = _load()
    seen: list[Any] = []
    granted = esc.approve_escalation(
        _request(),
        _approval(esc, approver=_Approver("allowed-once", seen)),
    )
    assert granted == "workspace-write"
    assert seen[0]["reason"] == (
        "escalate sandbox to workspace-write: the user asked to write in the workspace"
    )


def test_non_widening_never_asks() -> None:
    esc = _load()
    seen: list[Any] = []
    approval = _approval(esc, approver=_Approver("allowed-once", seen))
    try:
        esc.approve_escalation(_request(requested_mode="read-only"), approval)
    except ValueError as exc:
        assert 'not strictly wider than this call\'s current "read-only" mode' in str(exc)
    else:
        raise AssertionError("expected non-widening error")
    try:
        esc.approve_escalation(
            _request(requested_mode="workspace-write", effective_mode="danger-full-access"),
            approval,
        )
    except ValueError as exc:
        assert "not strictly wider" in str(exc)
    else:
        raise AssertionError("expected non-widening error")
    assert seen == []


def test_missing_approver_or_agent() -> None:
    esc = _load()
    try:
        esc.approve_escalation(_request(), _approval(esc, approver=None))
    except ValueError as exc:
        assert "no approval service is composed" in str(exc)
    else:
        raise AssertionError("expected missing approver error")
    try:
        esc.approve_escalation(_request(), _approval(esc, agent=None))
    except ValueError as exc:
        assert "no agent to route it through" in str(exc)
    else:
        raise AssertionError("expected missing agent error")


def test_outcome_texts() -> None:
    esc = _load()
    try:
        esc.approve_escalation(
            _request(subject="operation"),
            _approval(esc, approver=_Approver("rejected")),
        )
    except ValueError as exc:
        assert str(exc) == 'the user rejected escalating this operation to "workspace-write"'
    else:
        raise AssertionError("expected rejection")
    try:
        esc.approve_escalation(_request(), _approval(esc, approver=_Approver("cancelled")))
    except ValueError as exc:
        assert str(exc) == 'approval for escalating to "workspace-write" was cancelled'
    else:
        raise AssertionError("expected cancel")
    try:
        esc.approve_escalation(_request(), _approval(esc, approver=_Approver("unavailable")))
    except ValueError as exc:
        assert "no approval channel is available" in str(exc)
    else:
        raise AssertionError("expected unavailable")
    try:
        esc.approve_escalation(_request(), _approval(esc, approver=_Approver("bogus")))
    except ValueError:
        pass
    else:
        raise AssertionError("expected unknown outcome error")


if __name__ == "__main__":
    test_wider_ladder()
    test_validate_escalation_args()
    test_markers()
    test_grant_asks_with_audit_reason()
    test_non_widening_never_asks()
    test_missing_approver_or_agent()
    test_outcome_texts()
    print("escalation_test ok")
