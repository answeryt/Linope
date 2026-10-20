"""Handles granted to one capability process."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from kernel.resource.definition import (
    ResourceDefinition,
    ResourceGrant,
    validate_grants,
)
from kernel.resource.resource_contract import kind_name


@dataclass(frozen=True)
class ResourceContext:
    """The process-scoped, serializable view of granted resources."""

    process_id: str
    capability_id: str
    grants: tuple[ResourceGrant, ...]
    created_at: str
    settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        process_id: str,
        capability_id: str,
        requirements: tuple[ResourceDefinition, ...],
        grants: tuple[ResourceGrant, ...],
        settings: dict[str, Any] | None = None,
    ) -> "ResourceContext":
        validate_grants(requirements, grants)
        return cls(
            process_id=process_id,
            capability_id=capability_id,
            grants=grants,
            created_at=datetime.now(timezone.utc).isoformat(),
            settings=dict(settings or {}),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "process_id": self.process_id,
            "capability_id": self.capability_id,
            "created_at": self.created_at,
            "grants": [grant.payload() for grant in self.grants],
            "settings": dict(self.settings),
        }

    def get(self, resource_id: str) -> ResourceGrant:
        for grant in self.grants:
            if grant.resource_id == resource_id:
                return grant
        raise KeyError(resource_id)

    def get_handle(self, handle: str) -> ResourceGrant:
        for grant in self.grants:
            if grant.handle == handle:
                return grant
        raise KeyError(handle)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ResourceContext":
        grants = []
        for item in payload.get("grants") or ():
            grants.append(
                ResourceGrant(
                    resource_id="",
                    kind=kind_name(item["kind"]),
                    handle=str(item["handle"]),
                    call_params=dict(item.get("call_params") or {}),
                )
            )
        return cls(
            process_id=str(payload["process_id"]),
            capability_id=str(payload["capability_id"]),
            grants=tuple(grants),
            created_at=str(payload["created_at"]),
            settings=dict(payload.get("settings") or {}),
        )
