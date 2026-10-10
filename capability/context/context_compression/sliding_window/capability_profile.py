"""Process profile for the sliding-window context capability."""

from __future__ import annotations


def load(kind, body, call_params=None):
    """Load context content. This package chooses the compression function."""
    from pathlib import Path

    from capability.context import load_in_directory

    del call_params
    return load_in_directory(Path(__file__).resolve().parent, kind, body)


def capability_profile(capability_id, changes):
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.CONTEXT, identity={"id": capability_id}),
        ),
    )
