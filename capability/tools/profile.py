"""Resource claims for a tool process. The kernel does not choose the mode."""

from __future__ import annotations

import os

from kernel.environment.mount import project_identity, root_from
from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.resource.definition import ResourceKind


def workspace_tool(capability_id, changes, mode):
    """A tool that uses the project workspace in the sandbox mode the plugin names."""
    root = root_from(changes, os.getcwd())
    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
            ResourceClaim(
                kind=ResourceKind.SANDBOX,
                identity=project_identity(root),
                call_params={"mode": str(mode)},
            ),
        ),
    )


def network_tool(capability_id):
    """A tool that uses the ledger network and does not receive a workspace."""
    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
            ResourceClaim(kind=ResourceKind.NETWORK, identity={"channel": "ledger"}),
        ),
    )
