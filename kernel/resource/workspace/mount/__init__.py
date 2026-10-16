"""Mount space for one workspace lease."""

from kernel.resource.workspace.mount.kind import KIND, identity, root_from
from kernel.resource.workspace.mount.mode import (
    DANGER_FULL_ACCESS,
    READ_ONLY,
    WORKSPACE_WRITE,
    check_mode,
    confines,
    writes,
)
from kernel.resource.workspace.mount.view import admit_path, blocked, inside, private_temp

__all__ = [
    "DANGER_FULL_ACCESS",
    "KIND",
    "READ_ONLY",
    "WORKSPACE_WRITE",
    "admit_path",
    "blocked",
    "inside",
    "check_mode",
    "confines",
    "identity",
    "private_temp",
    "root_from",
    "writes",
]
