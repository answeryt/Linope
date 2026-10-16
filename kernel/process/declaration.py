"""Nested resource declaration used to create one capability process."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.resource.definition import ResourceDefinition, ResourceKind


@dataclass(frozen=True)
class ResourceClaim:
    """One resource the developer asks the pool to bind."""

    kind: ResourceKind
    identity: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, int | float | str] = field(default_factory=dict)
    call_params: dict[str, Any] = field(default_factory=dict)
    share_requested: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ResourceClaim":
        return cls(
            kind=ResourceKind(str(payload["kind"])),
            identity=dict(payload.get("identity") or {}),
            limits=dict(payload.get("limits") or {}),
            call_params=dict(payload.get("call_params") or {}),
            share_requested=bool(payload.get("share_requested", False)),
        )


@dataclass(frozen=True)
class ProcessDeclaration:
    """The only creation input: a capability plus nested resource claims.

    ``settings`` are call values such as provider, model id, and temperature.
    They are not a resource lease.
    """

    capability: str
    resources: tuple[ResourceClaim, ...] = ()
    settings: dict[str, Any] = field(default_factory=dict)

    def resource_definitions(self) -> tuple[ResourceDefinition, ...]:
        """The kinds this profile asked for. One definition per claim."""
        return tuple(
            ResourceDefinition(kind=claim.kind) for claim in self.resources
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ProcessDeclaration":
        raw_resources = payload.get("resources") or ()
        return cls(
            capability=str(payload["capability"]),
            resources=tuple(
                ResourceClaim.from_payload(item) for item in raw_resources
            ),
            settings=dict(payload.get("settings") or {}),
        )
