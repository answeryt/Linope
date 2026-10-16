"""Claims for peers that touch files or the network."""

from __future__ import annotations

import os

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.resource.definition import ResourceKind
from kernel.resource.network.kind import identity as network_identity
from kernel.resource.workspace.kind import identity as workspace_identity
from kernel.resource.workspace.kind import root_from


def tool_with_workspace(capability_id: str, changes) -> ProcessDeclaration:
    """A file, shell, or terminal process shares the project root."""
    root = root_from(changes, os.getcwd())
    mode = "workspace-write"
    for topic, raw in changes or ():
        if topic == "mode" and str(raw).strip():
            mode = str(raw)
    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
            ResourceClaim(
                kind=ResourceKind.WORKSPACE,
                identity=workspace_identity(root),
                call_params={"mode": mode},
            ),
        ),
    )


def tool_with_network(capability_id: str, names: tuple[str, ...]) -> ProcessDeclaration:
    """A network tool leases the named hosts. It does not receive a workspace."""
    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
            ResourceClaim(
                kind=ResourceKind.NETWORK,
                identity=network_identity(names),
            ),
        ),
    )
