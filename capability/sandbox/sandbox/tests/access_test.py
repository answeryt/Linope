from __future__ import annotations

from pathlib import Path

import pytest

from capability.sandbox.access import (
    HOST_SCOPE,
    WORKSPACE_WRITE,
    is_blocked,
    resolve_path,
    resolve_policy,
)


def test_host_policy_uses_runtime_cwd_as_hint_not_root(tmp_path: Path) -> None:
    policy = resolve_policy({"scope": HOST_SCOPE, "cwd": str(tmp_path)})

    assert policy["scope"] == HOST_SCOPE
    assert str(tmp_path.resolve()) == policy["cwd"]
    assert any(Path(root).anchor == Path(tmp_path).anchor for root in policy["roots"])
    assert resolve_path("child.txt", policy, write=True) == tmp_path / "child.txt"


def test_host_policy_keeps_sensitive_paths_blocked() -> None:
    policy = resolve_policy({"scope": HOST_SCOPE})

    assert is_blocked(Path(".env"), policy)
    with pytest.raises(PermissionError, match="blocked"):
        resolve_path(".env", policy, write=False)


def test_workspace_policy_stays_narrow_when_explicit(tmp_path: Path) -> None:
    policy = resolve_policy(
        {"scope": "workspace", "cwd": str(tmp_path), "mode": WORKSPACE_WRITE}
    )

    assert policy["roots"] == [str(tmp_path.resolve())]
    with pytest.raises(PermissionError, match="outside"):
        resolve_path(str(tmp_path.parent / "outside.txt"), policy, write=False)
