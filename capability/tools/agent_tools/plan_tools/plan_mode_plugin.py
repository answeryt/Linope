# -*- coding: utf-8 -*-
"""Present a plan for review and leave plan mode after Host approval."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "plan_mode"
PLUGIN_VERSION = "1.0"

ReviewFn = Callable[..., dict[str, Any]]

EXIT_PLAN_MODE_SCHEMA: dict[str, Any] = {
    "name": "exit_plan_mode",
    "description": (
        "Use only in plan mode. Present your plan for the user's review and, "
        "on approval, leave plan mode. Send the COMPLETE plan as markdown, "
        "starting with a # heading that names it. The user may approve "
        "(carry out the plan from your next step) or keep planning — their "
        "feedback comes back in the tool result; revise and present again."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "plan": {
                "type": "string",
                "description": "The complete plan, as markdown, starting with a # heading that names it.",
            },
        },
        "required": ["plan"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [EXIT_PLAN_MODE_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('exit_plan_mode', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "exit_plan_mode":
        return _error(f"unknown tool: {name}")
    return exit_plan_mode(str(arguments.get("plan") or ""), **kwargs)


def exit_plan_mode(
    plan: str,
    review: Optional[ReviewFn] = None,
    plan_mode_active: bool = True,
) -> str:
    """Submit `plan` for review. Host injects `review` and current mode."""
    if not plan.strip():
        return _error("plan must be a non-empty markdown document")
    if not plan.lstrip().startswith("#"):
        return _error("plan must start with a # heading that names it")
    if not plan_mode_active:
        return _error("exit_plan_mode is only valid while plan mode is active")
    if review is None:
        return json.dumps(
            {
                "success": True,
                "approved": False,
                "plan": plan,
                "message": (
                    "Plan captured. Host has not injected a review channel; "
                    "the user must switch modes manually to begin implementation."
                ),
            },
            ensure_ascii=False,
        )
    result = review(plan=plan)
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

