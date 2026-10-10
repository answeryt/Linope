"""Definitions and grants for resources owned by one capability process."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ResourceKind(StrEnum):
    CONTEXT = "context"
    MODEL = "model"
    MEMORY = "memory"
    WORKSPACE = "workspace"
    TOOL = "tool"
    NETWORK = "network"
    IDENTITY = "identity"
    PERSISTENCE = "persistence"
    LIFECYCLE = "lifecycle"
    COMMUNICATION = "communication"
    PROMPT = "prompt"


class ResourceShareMode(StrEnum):
    EXCLUSIVE = "exclusive"
    SHARED = "shared"


@dataclass(frozen=True)
class ResourceDefinition:
    """A capability's declaration of one resource kind it needs."""

    kind: ResourceKind
    required: bool = True
    share_mode: ResourceShareMode = ResourceShareMode.EXCLUSIVE
    limits: dict[str, int | float | str] = field(default_factory=dict)
    resource_id: str = ""


@dataclass(frozen=True)
class ResourceGrant:
    """A grant bound to a process. The child sees only the handle view."""

    resource_id: str
    kind: ResourceKind
    handle: str
    limits: dict[str, int | float | str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    call_params: dict[str, Any] = field(default_factory=dict)
    share_mode: ResourceShareMode = ResourceShareMode.EXCLUSIVE

    def process_payload(self) -> dict[str, Any]:
        """Serializable view handed to the capability process."""
        return {
            "handle": self.handle,
            "kind": self.kind.value,
            "limits": dict(self.limits),
            "call_params": dict(self.call_params),
        }

    def payload(self) -> dict[str, Any]:
        return self.process_payload()


def validate_grants(
    requirements: tuple[ResourceDefinition, ...],
    grants: tuple[ResourceGrant, ...],
) -> None:
    """Ensure the grants satisfy one capability's declared requirements."""
    handles = [grant.handle for grant in grants]
    if len(set(handles)) != len(handles):
        raise ValueError("Resource grants must have unique handles")

    if any(requirement.resource_id for requirement in requirements):
        _validate_by_resource_id(requirements, grants)
        return
    _validate_by_kind(requirements, grants)


def _validate_by_kind(
    requirements: tuple[ResourceDefinition, ...],
    grants: tuple[ResourceGrant, ...],
) -> None:
    granted = {grant.kind for grant in grants}
    if len(granted) != len(grants):
        raise ValueError("Resource grants must have unique kinds")
    for requirement in requirements:
        if requirement.required and requirement.kind not in granted:
            raise ValueError(
                f"Missing required resource grant: {requirement.kind.value}"
            )
    allowed = {requirement.kind for requirement in requirements}
    unknown = granted - allowed
    if unknown:
        names = ", ".join(sorted(kind.value for kind in unknown))
        raise ValueError(f"Capability received undeclared resources: {names}")


def _validate_by_resource_id(
    requirements: tuple[ResourceDefinition, ...],
    grants: tuple[ResourceGrant, ...],
) -> None:
    by_id = {grant.resource_id: grant for grant in grants}
    if len(by_id) != len(grants):
        raise ValueError("Resource grants must have unique resource ids")
    for requirement in requirements:
        grant = by_id.get(requirement.resource_id)
        if grant is None:
            if requirement.required:
                raise ValueError(
                    f"Missing required resource grant: {requirement.resource_id}"
                )
            continue
        if grant.kind != requirement.kind:
            raise TypeError(
                f"Resource {requirement.resource_id!r} expects "
                f"{requirement.kind.value}, got {grant.kind.value}"
            )
    known = {requirement.resource_id for requirement in requirements}
    unknown = set(by_id) - known
    if unknown:
        raise ValueError(
            f"Capability received undeclared resources: {', '.join(sorted(unknown))}"
        )
