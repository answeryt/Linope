"""Compile a resource declaration into pool entity keys."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from kernel.resource.definition import ResourceShareMode
from kernel.resource.resource_contract import kind_name, validate_claim


class ResourceDeclaration(Protocol):
    """Minimal declaration surface required by the resource compiler."""

    resources: tuple[Any, ...]

    def resource_definitions(self) -> tuple[Any, ...]:
        ...


@dataclass(frozen=True)
class CompiledResource:
    """One entity binding produced from a claim. Handles are minted later."""

    kind: str
    resource_id: str
    identity: dict[str, Any]
    call_params: dict[str, Any]
    share_mode: ResourceShareMode
    share_granted: bool


def entity_key(
    kind: str,
    identity: dict[str, Any],
    *,
    pid: int | None = None,
) -> str:
    """Hash kind and identity. Call params never enter the key."""
    body: dict[str, Any] = {
        "kind": kind_name(kind),
        "identity": identity,
    }
    if pid is not None:
        body["pid"] = pid
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
    pid: int,
    *,
    shared: tuple[str, ...] = (),
) -> tuple[CompiledResource, ...]:
    """Resolve claims into entity keys.

    ``shared`` names the kinds this launch actually shares. A kind that is
    only allowed to be shared still stays exclusive until it is named.
    """
    requirements = declaration.resource_definitions()
    claims_by_kind = {}
    for claim in declaration.resources:
        name = kind_name(claim.kind)
        if name in claims_by_kind:
            raise ValueError(f"Duplicate resource claim for {name}")
        claims_by_kind[name] = claim

    required = {kind_name(item.kind) for item in requirements if item.required}
    missing = required - set(claims_by_kind)
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"Declaration is missing required resources: {names}")

    allowed = {kind_name(item.kind) for item in requirements}
    unknown = set(claims_by_kind) - allowed
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"Capability received undeclared resources: {names}")

    shared_names = {kind_name(item) for item in shared}
    compiled: list[CompiledResource] = []
    for requirement in requirements:
        name = kind_name(requirement.kind)
        claim = claims_by_kind.get(name)
        if claim is None:
            continue
        sharing = name in shared_names
        validate_claim(name, dict(claim.identity), shared=sharing)
        if sharing:
            share_mode = ResourceShareMode.SHARED
            share_granted = True
            resource_id = entity_key(name, claim.identity)
        else:
            share_mode = ResourceShareMode.EXCLUSIVE
            share_granted = False
            resource_id = entity_key(
                name,
                claim.identity,
                pid=pid,
            )
        compiled.append(
            CompiledResource(
                kind=name,
                resource_id=resource_id,
                identity=dict(claim.identity),
                call_params=dict(claim.call_params),
                share_mode=share_mode,
                share_granted=share_granted,
            )
        )
    return tuple(compiled)
