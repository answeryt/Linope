"""Host-only helpers for declaring model capability contracts.

Leaf plugins must not import this module. They publish a literal
``MODEL_CAPABILITY`` dict instead.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .capability_contract import CapabilityContract


def model_capability(
    name: str,
    *,
    provides: Iterable[str] | None = None,
    requires: Iterable[Any] = (),
    kind: str = "model.capability",
    constraints: Mapping[str, Any] | None = None,
    version: str = "1.0",
    **metadata: Any,
) -> CapabilityContract:
    return CapabilityContract(
        name,
        version=version,
        provides=provides,
        requires=requires,
        kind=kind,
        constraints=constraints,
        metadata=metadata,
    )


def model_interface(
    name: str,
    *,
    requires: Iterable[Any] = (),
    constraints: Mapping[str, Any] | None = None,
) -> CapabilityContract:
    return model_capability(
        f"model.interface.{name}",
        requires=requires,
        kind="model.interface",
        constraints=constraints,
        interface=name,
    )


def model_parameter(name: str, *, provides: Iterable[str] | None = None) -> CapabilityContract:
    specific = f"model.parameters.{name}"
    return model_capability(
        specific,
        provides=["model.parameters", *(provides or (specific,))],
        kind="model.parameter",
    )


def model_fallback(name: str, *, requires: Iterable[Any] = ()) -> CapabilityContract:
    return model_capability(
        f"model.fallback.{name}",
        requires=requires,
        kind="model.fallback",
    )


def model_message(name: str, *, provides: Iterable[str] | None = None) -> CapabilityContract:
    return model_capability(
        f"model.message.{name}",
        provides=provides,
        kind="model.message",
    )


def model_token(name: str, *, provides: Iterable[str] | None = None) -> CapabilityContract:
    return model_capability(
        f"model.tokens.{name}",
        provides=provides,
        kind="model.token",
    )


def model_provider(
    provider: str,
    *,
    interface: str,
    card_id: str | None = None,
    constraints: Mapping[str, Any] | None = None,
) -> CapabilityContract:
    return model_capability(
        f"model.provider.{card_id or provider}",
        provides=[f"model.provider.{provider}", "model.provider"],
        requires=[f"model.interface.{interface}"],
        kind="model.provider",
        constraints=constraints,
        provider=provider,
        interface=interface,
        card_id=card_id or provider,
    )


def model_thread(*, requires: Iterable[Any]) -> CapabilityContract:
    return model_capability(
        "model.thread",
        requires=requires,
        kind="model.thread",
        constraints={"domain": "model"},
    )


__all__ = [
    "model_capability",
    "model_fallback",
    "model_interface",
    "model_message",
    "model_parameter",
    "model_provider",
    "model_thread",
    "model_token",
]
