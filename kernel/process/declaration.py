"""Nested resource declaration used to create one capability process."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from kernel.communication.address import CLASSES
from kernel.resource.definition import ResourceDefinition
from kernel.resource.resource_contract import kind_name, require


@dataclass(frozen=True)
class ResourceClaim:
    """One resource the developer asks the pool to bind."""

    kind: str
    identity: dict[str, Any] = field(default_factory=dict)
    call_params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ResourceClaim":
        return cls(
            kind=str(payload["kind"]),
            identity=dict(payload.get("identity") or {}),
            call_params=dict(payload.get("call_params") or {}),
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


def stamp_memory_space(declaration: ProcessDeclaration, changes) -> ProcessDeclaration:
    """Copy ``--change space=`` onto the memory claim before the lease is compiled."""
    space = ""
    for topic, raw in changes or ():
        if topic == "space" and str(raw).strip():
            space = str(raw).strip()
    if not space:
        return declaration
    for part in space.replace(" ", "").split(","):
        if part not in CLASSES:
            raise ValueError(f"Unknown memory class: {part or space}")
    updated: list[ResourceClaim] = []
    for claim in declaration.resources:
        if kind_name(claim.kind) != "memory":
            updated.append(claim)
            continue
        params = dict(claim.call_params)
        params["space"] = space
        updated.append(replace(claim, call_params=params))
    return replace(declaration, resources=tuple(updated))


def append_chosen(
    declaration: ProcessDeclaration,
    chosen: tuple[str, ...],
) -> ProcessDeclaration:
    """Add resources the profile did not already claim.

    A kind that is already on the declaration stays as the profile wrote it.
    """
    if not chosen:
        return declaration
    existing = {kind_name(item.kind) for item in declaration.resources}
    added: list[ResourceClaim] = []
    for raw in chosen:
        claim = _chosen_claim(raw, existing)
        added.append(claim)
        existing.add(kind_name(claim.kind))
    return replace(declaration, resources=(*declaration.resources, *added))


def _chosen_claim(raw: str, existing: set[str]) -> ResourceClaim:
    kind, sep, value = str(raw).partition("=")
    name = kind_name(kind.strip())
    identity_value = value.strip()
    if not sep or not name or not identity_value:
        raise ValueError("Missing identity")
    if name in existing:
        raise ValueError(f"Cannot change the default resource: {name}")
    contract = require(name)
    if len(contract.required_identity_keys) != 1:
        missing = ", ".join(contract.required_identity_keys)
        raise ValueError(f"{name} is missing identity: {missing}")
    return ResourceClaim(
        kind=name,
        identity={contract.required_identity_keys[0]: identity_value},
    )
