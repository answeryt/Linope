"""Compile a resource declaration into pool entity keys."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from kernel.resource.definition import ResourceKind, ResourceShareMode


class ResourceDeclaration(Protocol):
    """Minimal declaration surface required by the resource compiler."""

    resources: tuple[Any, ...]

    def resource_definitions(self) -> tuple[Any, ...]:
        ...


@dataclass(frozen=True)
class CompiledResource:
    """One entity binding produced from a claim. Handles are minted later."""

    kind: ResourceKind
    resource_id: str
    identity: dict[str, Any]
    limits: dict[str, int | float | str]
    call_params: dict[str, Any]
    share_mode: ResourceShareMode
    share_granted: bool


def entity_key(
    kind: ResourceKind,
    identity: dict[str, Any],
    *,
    process_id: str | None = None,
) -> str:
    """Hash kind and identity. Call params never enter the key."""
    body: dict[str, Any] = {
        "kind": kind.value,
        "identity": identity,
    }
    if process_id is not None:
        body["process_id"] = process_id
    encoded = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def compile_declaration(
    declaration: ResourceDeclaration,
    process_id: str,
    *,
    shared: bool = False,
) -> tuple[CompiledResource, ...]:
    """Resolve claims into entity keys. Sharing follows the capability list."""
    requirements = declaration.resource_definitions()
    claims_by_kind = {}
    for claim in declaration.resources:
        if claim.kind in claims_by_kind:
            raise ValueError(f"Duplicate resource claim for {claim.kind.value}")
        claims_by_kind[claim.kind] = claim

    required = {item.kind for item in requirements if item.required}
    missing = required - set(claims_by_kind)
    if missing:
        names = ", ".join(sorted(kind.value for kind in missing))
        raise ValueError(f"Declaration is missing required resources: {names}")

    allowed = {item.kind for item in requirements}
    unknown = set(claims_by_kind) - allowed
    if unknown:
        names = ", ".join(sorted(kind.value for kind in unknown))
        raise ValueError(f"Capability received undeclared resources: {names}")

    compiled: list[CompiledResource] = []
    for requirement in requirements:
        claim = claims_by_kind.get(requirement.kind)
        if claim is None:
            continue
        if shared:
            share_mode = ResourceShareMode.SHARED
            share_granted = True
            resource_id = entity_key(requirement.kind, claim.identity)
        else:
            share_mode = ResourceShareMode.EXCLUSIVE
            share_granted = False
            resource_id = entity_key(
                requirement.kind,
                claim.identity,
                process_id=process_id,
            )
        compiled.append(
            CompiledResource(
                kind=requirement.kind,
                resource_id=resource_id,
                identity=dict(claim.identity),
                limits=dict(claim.limits),
                call_params=dict(claim.call_params),
                share_mode=share_mode,
                share_granted=share_granted,
            )
        )
    return tuple(compiled)
