"""Claims for peers that touch files or talk to other processes."""

from __future__ import annotations

import os

from kernel.environment.mount import project_identity, root_from
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.resource.definition import ResourceKind


def tool_with_workspace(capability_id: str, changes) -> ProcessDeclaration:
    """A file, shell, or terminal process leases a tool and a sandbox."""
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
                kind=ResourceKind.SANDBOX,
                identity=project_identity(root),
                call_params={"mode": mode},
            ),
            ResourceClaim(
                kind=ResourceKind.NETWORK,
                identity={"channel": "ledger"},
            ),
        ),
    )


def tool_only(capability_id: str) -> ProcessDeclaration:
    """A tool without a sandbox. It can still be addressed on the ledger channel."""
    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
            ResourceClaim(kind=ResourceKind.NETWORK, identity={"channel": "ledger"}),
        ),
    )
