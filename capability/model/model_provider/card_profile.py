"""Turn a model plugin card into a process declaration."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from kernel.process.declaration import ProcessDeclaration

UNSET = "UNSET"


def declaration_from_card(
    capability_id: str,
    card: dict[str, Any],
    changes: Sequence[tuple[str, str]],
) -> ProcessDeclaration:
    """Use the card as the base, then apply change clauses this card understands."""
    identity = {"provider": card["provider"], "id": card["model"]}
    parameters = dict(card.get("parameters") or {})
    call_params = {
        key: value for key, value in parameters.items() if value != UNSET
    }
    known = set(parameters) | {"model", "provider"}
    for topic, raw in changes:
        if topic not in known:
            raise ValueError(f"不认识的主题: {topic}")
        value = _parse_value(raw)
        if topic == "model":
            identity["id"] = value
        elif topic == "provider":
            identity["provider"] = value
        else:
            call_params[topic] = value
    settings = {"provider": identity["provider"], "id": identity["id"]}
    settings.update(call_params)
    return ProcessDeclaration(
        capability=capability_id,
        resources=(),
        settings=settings,
    )


def _parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
