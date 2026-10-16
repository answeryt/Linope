"""File modes for one workspace view.

``danger-full-access`` means an external command is not wrapped.
"""

from __future__ import annotations

READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
DANGER_FULL_ACCESS = "danger-full-access"

MODES = (READ_ONLY, WORKSPACE_WRITE, DANGER_FULL_ACCESS)
CONFINED = (READ_ONLY, WORKSPACE_WRITE)


def check_mode(mode: str) -> str:
    """Reject an unknown file mode."""
    if mode not in MODES:
        raise ValueError("文件模式只能是只读、工作区可写，或跳过包装")
    return mode


def writes(mode: str) -> bool:
    """Whether the workspace root itself may be changed."""
    return mode in {WORKSPACE_WRITE, DANGER_FULL_ACCESS}


def confines(mode: str) -> bool:
    """Whether an external command must be wrapped."""
    return mode in CONFINED
