"""The resource context injected into one capability process."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from kernel.resource.definition import (
    ResourceDefinition,
    ResourceGrant,
    ResourceKind,
    validate_grants,
)


@dataclass(frozen=True)
class ResourceContext:
    """The process-scoped, serializable view of granted resources."""

    process_id: str
    capability_id: str
    grants: tuple[ResourceGrant, ...]
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        process_id: str,
        capability_id: str,
        requirements: tuple[ResourceDefinition, ...],
        grants: tuple[ResourceGrant, ...],
    ) -> "ResourceContext":
        validate_grants(requirements, grants)
        return cls(
            process_id=process_id,
            capability_id=capability_id,
            grants=grants,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def payload(self) -> dict[str, Any]:
        return {
            "process_id": self.process_id,
            "capability_id": self.capability_id,
            "created_at": self.created_at,
            "grants": [grant.payload() for grant in self.grants],
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
        grants = tuple(
            ResourceGrant(
                resource_id="",
                kind=ResourceKind(str(item["kind"])),
                handle=str(item["handle"]),
                limits=dict(item.get("limits") or {}),
                call_params=dict(item.get("call_params") or {}),
            )
            for item in payload.get("grants") or ()
        )
        return cls(
            process_id=str(payload["process_id"]),
            capability_id=str(payload["capability_id"]),
            grants=grants,
            created_at=str(payload["created_at"]),
        )
