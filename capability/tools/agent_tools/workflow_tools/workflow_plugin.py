# -*- coding: utf-8 -*-
"""Foreground workflow script that orchestrates Host-injected child agents."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "workflow"
PLUGIN_VERSION = "1.0"

RunFn = Callable[..., dict[str, Any]]

WORKFLOW_SCHEMA: dict[str, Any] = {
    "name": "workflow",
    "description": (
        "Run a JavaScript workflow script that orchestrates subagents at scale. "
        "Use this for work that fans out across many independent pieces. The "
        "workflow's identity rides the `meta` parameter as JSON: required `name` "
        "and `description`. The `script` parameter is the plain JavaScript body "
        "ONLY. The run executes in the foreground."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "script": {
                "type": "string",
                "description": (
                    "The plain-JS workflow script body (top-level await allowed; "
                    "NO `export const meta` statement; end with `return <json-value>`)."
                ),
            },
            "meta": {
                "type": "object",
                "description": "The workflow identity block (plain JSON — never code).",
                "additionalProperties": True,
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Short kebab-case workflow name.",
                    },
                    "description": {
                        "type": "string",
                        "description": "One-line description of what the workflow does.",
                    },
                    "whenToUse": {
                        "type": "string",
                        "description": "Optional guidance on when this workflow applies.",
                    },
                    "phases": {
                        "type": "array",
                        "description": "Optional phase declarations matched by phase() calls.",
                        "items": {
                            "type": "object",
                            "additionalProperties": True,
                            "properties": {
                                "title": {"type": "string"},
                                "detail": {"type": "string"},
                                "provider": {"type": "string"},
                                "model": {"type": "string"},
                            },
                            "required": ["title"],
                        },
                    },
                },
                "required": ["name", "description"],
            },
            "args": {
                "type": "object",
                "description": (
                    "Optional JSON input exposed to the script as the `args` global."
                ),
                "additionalProperties": True,
            },
        },
        "required": ["script", "meta"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [WORKFLOW_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch('workflow', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "workflow":
        return _error(f"unknown tool: {name}")
    return workflow(
        str(arguments.get("script") or ""),
        arguments.get("meta") or {},
        arguments.get("args"),
        **kwargs,
    )


def workflow(
    script: str,
    meta: dict[str, Any],
    args: Optional[dict[str, Any]] = None,
    run: Optional[RunFn] = None,
) -> str:
    """Validate identity and hand the script to the Host workflow engine."""
    if not script.strip():
        return _error("script must be a non-empty JavaScript body")
    if not isinstance(meta, dict):
        return _error("meta must be a JSON object")
    name = str(meta.get("name") or "").strip()
    description = str(meta.get("description") or "").strip()
    if not name or not description:
        return _error("meta.name and meta.description are required")
    if run is None:
        return _error(
            "No workflow engine is attached. Host must inject a `run` "
            "callback that executes the script against child agents."
        )
    result = run(script=script, meta=meta, args=args or {})
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

