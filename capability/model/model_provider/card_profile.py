"""Turn a model plugin card into a process declaration."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any

from kernel.environment.mount import project_identity
from kernel.environment.sandbox_vocab import check_mode
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.resource.definition import ResourceKind

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
    permission, capabilities, kept = _permission_changes(changes)
    known = set(parameters) | {"model", "provider"}
    for topic, raw in kept:
        if topic not in known:
            raise ValueError(f"Unknown topic: {topic}")
        value = _parse_value(raw)
        if topic == "model":
            identity["id"] = value
        elif topic == "provider":
            identity["provider"] = value
        else:
            call_params[topic] = value
    settings = {"provider": identity["provider"], "id": identity["id"]}
    settings.update(call_params)
    resources = [
        ResourceClaim(
            kind=ResourceKind.NETWORK,
            identity={"channel": "ledger"},
        )
    ]
    if permission is not None:
        settings["permission"] = permission
        resources.append(
            ResourceClaim(
                kind=ResourceKind.SANDBOX,
                identity=project_identity(os.getcwd()),
                call_params={"mode": permission},
            )
        )
    if capabilities is not None:
        settings["capabilities"] = capabilities
    return ProcessDeclaration(
        capability=capability_id,
        resources=tuple(resources),
        settings=settings,
    )


def _permission_changes(
    changes: Sequence[tuple[str, str]],
) -> tuple[str | None, list[str] | None, list[tuple[str, str]]]:
    """Pull model-only permission fields out of the model API parameters."""
    permission = None
    capabilities = None
    kept: list[tuple[str, str]] = []
    for topic, raw in changes:
        if topic == "permission":
            permission = check_mode(str(raw))
        elif topic == "capabilities":
            capabilities = _capability_names(raw)
        else:
            kept.append((topic, raw))
    return permission, capabilities, kept


def _capability_names(raw: str) -> list[str]:
    value = _parse_value(raw)
    if isinstance(value, str):
        names = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, list):
        names = [str(item).strip() for item in value if str(item).strip()]
    else:
        raise ValueError("capabilities must be tool names")
    return names


def _parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
