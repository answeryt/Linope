# -*- coding: utf-8 -*-
"""Ask the user a question and wait for a Host-injected answer provider."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "ask_user"
PLUGIN_VERSION = "1.0"

AskFn = Callable[..., dict[str, Any]]

ASK_USER_SCHEMA: dict[str, Any] = {
    "name": "ask_user_question",
    "description": (
        "Ask the user a concise question when you need confirmation, a choice, "
        "or missing information before proceeding. Send one or more questions, "
        "each with a stable id that will be echoed in the answer."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "description": "Questions to ask the user before continuing.",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Stable id for this question; echoed in the answer.",
                        },
                        "question": {
                            "type": "string",
                            "description": "The specific question to ask the user.",
                        },
                        "header": {
                            "type": "string",
                            "description": 'Optional short heading, such as "Confirm" or "Choose Mode".',
                        },
                        "options": {
                            "type": "array",
                            "description": (
                                "Optional choices to show the user. If you recommend "
                                'one, put it first and append "(Recommended)" to that label.'
                            ),
                            "items": {
                                "type": "object",
                                "additionalProperties": True,
                                "properties": {
                                    "label": {
                                        "type": "string",
                                        "description": "Short user-facing option label.",
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "One sentence explaining the tradeoff or impact.",
                                    },
                                },
                                "required": ["label"],
                            },
                        },
                        "multi_select": {
                            "type": "boolean",
                            "description": "Whether the user may select more than one option. Defaults to false.",
                        },
                    },
                    "required": ["id", "question"],
                },
            },
        },
        "required": ["questions"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [ASK_USER_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"This process cannot load {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool content must be a mapping")
    return dispatch('ask_user_question', body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "ask_user_question":
        return _error(f"unknown tool: {name}")
    return ask_user_question(arguments.get("questions") or [], **kwargs)


def ask_user_question(questions: list[Any], ask: Optional[AskFn] = None) -> str:
    """Pause until the Host-injected `ask` provider returns answers."""
    if not isinstance(questions, list) or not questions:
        return _error("questions must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    for item in questions:
        if not isinstance(item, dict) or not item.get("id") or not item.get("question"):
            return _error("each question needs id and question")
        normalized.append(item)
    if ask is None:
        return _error(
            "No question provider is attached. Host must inject an `ask` "
            "callback that returns {answers: [{id, selected, custom?}]}."
        )
    result = ask(questions=normalized)
    answers = result.get("answers") if isinstance(result, dict) else None
    if not isinstance(answers, list):
        return _error("question provider returned no answers")
    return json.dumps({"success": True, "answers": answers}, ensure_ascii=False)


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

