# -*- coding: utf-8 -*-
"""Keep workspace and private-temp ACL capabilities from overlapping."""

from __future__ import annotations

import os
from collections.abc import Sequence


PLUGIN_NAME = "sandbox_windows_acl_path_boundary"
PLUGIN_VERSION = "1.0"


def contains_directory(root: str, candidate: str) -> bool:
    relation = os.path.relpath(os.path.realpath(candidate), os.path.realpath(root))
    return relation in {"", "."} or (
        not os.path.isabs(relation)
        and relation != ".."
        and not relation.startswith(".." + os.sep)
    )


def assert_temp_root_outside_workspace(workspace_root: str, temp_root: str) -> None:
    if contains_directory(workspace_root, temp_root):
        raise ValueError(
            "Windows ACL temp root must be outside the workspace: "
            f"workspace={workspace_root}; temp={temp_root}"
        )


def assert_private_temp_disjoint(writable_dirs: Sequence[str], temp_dir: str) -> None:
    for writable in writable_dirs:
        if contains_directory(writable, temp_dir) or contains_directory(temp_dir, writable):
            raise ValueError(
                "AclSandbox private temp directory must be disjoint from writable "
                f"directories: writable={writable}; temp={temp_dir}"
            )
