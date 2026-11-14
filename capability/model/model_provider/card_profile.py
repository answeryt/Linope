"""Turn a provider card into the model scheduler configuration."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

UNSET = "UNSET"


@dataclass(frozen=True)
class ModelConfiguration:
    """The effective configuration installed in the model resource."""

    capability: str
    card_id: str
    provider: str
    model: str
    context_limit: int
    call_params: dict[str, Any] = field(default_factory=dict)
    api_key_env: str = ""


def declaration_from_card(
    capability_id: str,
    card: dict[str, Any],
    changes: Sequence[tuple[str, str]],
) -> ModelConfiguration:
    """Use the card as the base, then apply changes understood by the card."""
    provider = str(card["provider"])
    model_name = str(card["model"])
    parameters = dict(card.get("parameters") or {})
    call_params = {
        key: value for key, value in parameters.items() if value != UNSET
    }
    known = set(parameters) | {
        "model",
        "provider",
        "base_url",
        "permission",
        "capabilities",
    }
    for topic, raw in changes:
        if topic not in known:
            raise ValueError(f"Unknown topic: {topic}")
        value = _parse_value(raw)
        if topic == "capabilities" and isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        if topic == "model":
            model_name = str(value)
        elif topic == "provider":
            provider = str(value)
        else:
            call_params[topic] = value
    from capability.model.model_API.model_paramaters.context_limits.context_limits import (
        resolve_default_context_length,
    )

    if "base_url" not in call_params and card.get("base_url") not in (None, UNSET):
        call_params["base_url"] = card["base_url"]
    call_params["model"] = model_name
    return ModelConfiguration(
        capability=capability_id,
        card_id=str(card.get("card_id") or capability_id.split(".")[-1]),
        provider=provider,
        model=model_name,
        context_limit=resolve_default_context_length(model_name),
        call_params=call_params,
        api_key_env=str(card.get("api_key_env") or ""),
    )


model_configuration_from_card = declaration_from_card


def _parse_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
