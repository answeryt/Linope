# -*- coding: utf-8 -*-
"""Child-scoped report channel back to the parent agent."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "subagent_report"
PLUGIN_VERSION = "1.0"

DeliverFn = Callable[..., dict[str, Any]]

REPORT_SCHEMA: dict[str, Any] = {
    "name": "report",
    "description": (
        "Report selected content to the agent that started you. Call this once "
        "before you finish, with a self-contained final result, and earlier for "
        "progress or findings that change what that agent does next. That agent "
        "shares your workspace but does not automatically receive your transcript. "
        "Reporting does not end your turn."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "output": {
                "type": "string",
                "description": (
                    "Actionable content for your parent; summarize conclusions "
                    "and reference relevant shared paths."
                ),
            },
        },
        "required": ["output"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [REPORT_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('report', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "report":
        return _error(f"unknown tool: {name}")
    return report(str(arguments.get("output") or ""), **kwargs)


def report(output: str, deliver: Optional[DeliverFn] = None) -> str:
    """Deliver `output` to the direct parent through the Host channel."""
    if not output.strip():
        return _error("output must be a non-empty string")
    if deliver is None:
        return _error(
            "report is only available inside a continuable child agent. "
            "Host must inject a `deliver(output)` callback."
        )
    result = deliver(output=output)
    return json.dumps({"success": True, **result}, ensure_ascii=False)


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)

def capability_profile(capability_id, changes):
    """Tell the process this tool needs a tool resource."""
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
        ),
    )

