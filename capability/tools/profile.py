"""Resource claims for a tool process. The kernel does not choose the mode."""

from __future__ import annotations

from kernel.process.declaration import ProcessDeclaration, ResourceClaim
from kernel.resource.definition import ResourceKind


def workspace_tool(capability_id, changes, mode):
    """A tool whose runtime host scope is resolved by capability/sandbox."""
    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
            ResourceClaim(
                kind=ResourceKind.SANDBOX,
                identity={"root": "host"},
                call_params={"mode": str(mode), "scope": "host"},
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
