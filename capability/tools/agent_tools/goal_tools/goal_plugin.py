# -*- coding: utf-8 -*-
"""Same-session completion goals: create, read, and update one revisioned goal."""

from __future__ import annotations

import json
import threading
import uuid
from typing import Any, Optional


ACTIONS = ("edit", "pause", "resume", "complete", "blocked")
MIN_BLOCKED_ROUNDS = 3

_GOALS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


CREATE_GOAL_SCHEMA: dict[str, Any] = {
    "name": "create_goal",
    "description": (
        "Create one persisted same-session completion goal when the current "
        "direct human request is a long-running objective that should continue "
        "across autonomous goal rounds. Do not use this for trivial single-turn work."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "objective": {
                "type": "string",
                "description": "The concrete completion objective inferred from the direct human request.",
            },
            "max_goal_rounds": {
                "type": "number",
                "description": "Optional positive safe-integer limit on automatic continuation rounds.",
            },
        },
        "required": ["objective"],
    },
}

GET_GOAL_SCHEMA: dict[str, Any] = {
    "name": "get_goal",
    "description": (
        "Read the current same-session goal, including its exact id/revision, "
        "objective, phase, completed continuation rounds, round limit, blocker "
        "reason when present, and whether another continuation is armed."
    ),
    "parameters": {"type": "object", "properties": {}},
}

UPDATE_GOAL_SCHEMA: dict[str, Any] = {
    "name": "update_goal",
    "description": (
        "Update the exact current goal revision. edit, pause, and resume require "
        "a direct top-level human request. During an automatic continuation of "
        "the current goal, complete and blocked are also allowed."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "goal_id": {"type": "string", "description": "Exact id returned by get_goal."},
            "revision": {
                "type": "number",
                "description": "Exact positive revision returned by get_goal.",
            },
            "action": {
                "type": "string",
                "enum": list(ACTIONS),
                "description": "edit | pause | resume | complete | blocked",
            },
            "objective": {
                "type": "string",
                "description": "Replacement objective; valid only with action edit.",
            },
            "max_goal_rounds": {
                "type": "number",
                "description": "Replacement cap; valid only with action edit.",
            },
            "blocked_reason": {
                "type": "string",
                "description": "Concrete blocking condition; required only with action blocked.",
            },
        },
        "required": ["goal_id", "revision", "action"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [CREATE_GOAL_SCHEMA, GET_GOAL_SCHEMA, UPDATE_GOAL_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. The body names which tool this plugin runs."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict) or "name" not in body:
        raise TypeError("tool 的内容必须带上 name")
    tool_name = str(body["name"])
    arguments = {key: value for key, value in body.items() if key != "name"}
    return dispatch(tool_name, arguments, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name == "create_goal":
        return create_goal(
            str(arguments.get("objective") or ""),
            arguments.get("max_goal_rounds"),
            **kwargs,
        )
    if name == "get_goal":
        return get_goal(**kwargs)
    if name == "update_goal":
        return update_goal(
            str(arguments.get("goal_id") or ""),
            arguments.get("revision"),
            str(arguments.get("action") or ""),
            arguments.get("objective"),
            arguments.get("max_goal_rounds"),
            arguments.get("blocked_reason"),
            **kwargs,
        )
    return _error(f"unknown tool: {name}")


def create_goal(
    objective: str,
    max_goal_rounds: Optional[float] = None,
    session_id: Optional[str] = None,
) -> str:
    if not objective.strip():
        return _error("objective must be a non-empty string")
    if max_goal_rounds is not None and (
        not isinstance(max_goal_rounds, (int, float))
        or int(max_goal_rounds) < 1
        or int(max_goal_rounds) != max_goal_rounds
    ):
        return _error("max_goal_rounds must be a positive safe integer")
    key = session_id or "default"
    record = {
        "id": uuid.uuid4().hex[:12],
        "revision": 1,
        "objective": objective.strip(),
        "phase": "active",
        "completedRounds": 0,
        "maxGoalRounds": int(max_goal_rounds) if max_goal_rounds is not None else None,
        "blockedReason": None,
        "continuationArmed": True,
    }
    with _LOCK:
        _GOALS[key] = record
    return json.dumps({"success": True, "goal": record}, ensure_ascii=False)


def get_goal(session_id: Optional[str] = None) -> str:
    key = session_id or "default"
    with _LOCK:
        record = _GOALS.get(key)
    if record is None:
        return json.dumps({"success": True, "goal": None}, ensure_ascii=False)
    return json.dumps({"success": True, "goal": record}, ensure_ascii=False)


def update_goal(
    goal_id: str,
    revision: Any,
    action: str,
    objective: Optional[str] = None,
    max_goal_rounds: Optional[float] = None,
    blocked_reason: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    if action not in ACTIONS:
        return _error(f"unknown action: {action}")
    key = session_id or "default"
    with _LOCK:
        record = _GOALS.get(key)
        if record is None or record["id"] != goal_id:
            return _error("goal_id does not match the current session goal")
        if int(revision or 0) != record["revision"]:
            return _error("revision does not match the current goal")
        if action == "edit":
            if not objective or not str(objective).strip():
                return _error("edit requires objective")
            record["objective"] = str(objective).strip()
            if max_goal_rounds is not None:
                record["maxGoalRounds"] = int(max_goal_rounds)
        elif action == "pause":
            record["phase"] = "paused"
            record["continuationArmed"] = False
        elif action == "resume":
            record["phase"] = "active"
            record["continuationArmed"] = True
        elif action == "complete":
            record["phase"] = "completed"
            record["continuationArmed"] = False
        elif action == "blocked":
            if record["completedRounds"] < MIN_BLOCKED_ROUNDS:
                return _error(
                    f"blocked is rejected before {MIN_BLOCKED_ROUNDS} admitted rounds"
                )
            if not blocked_reason or not str(blocked_reason).strip():
                return _error("blocked requires blocked_reason")
            record["phase"] = "blocked"
            record["blockedReason"] = str(blocked_reason).strip()
            record["continuationArmed"] = False
        record["revision"] += 1
        snapshot = dict(record)
    return json.dumps({"success": True, "goal": snapshot}, ensure_ascii=False)


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

