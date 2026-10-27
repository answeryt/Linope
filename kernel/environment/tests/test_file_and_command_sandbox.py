"""FileDoor and ComputeDoor follow capability/sandbox instead of a second policy."""

import os
import sys
from pathlib import Path

import pytest

from kernel.environment import HostExecutionPolicy, KernelEnvironment, ProcessEnvironment
from kernel.environment.file_io import FileDoor
from kernel.environment.filesystem import FilesystemView
from kernel.environment.mount import MODES, inside
from kernel.environment.sandbox_vocab import MODES as SANDBOX_MODES
from kernel.environment.sandbox_vocab import writable_roots


def _room(path: Path, mode: str, *, confine: bool = True) -> KernelEnvironment:
    shell = ProcessEnvironment.current(
        pid=os.getpid(),
        capability_id="tools.write",
        cwd=path,
    )
    return KernelEnvironment.build(
        shell=shell,
        policy=HostExecutionPolicy(),
        max_concurrent_tasks=1,
        max_sync_workers=1,
        access_mode=mode,
        confine=confine,
    )


def test_modes_and_writable_roots_come_from_the_sandbox(tmp_path: Path) -> None:
    source = (Path(__file__).resolve().parents[3] / "kernel" / "environment" / "mount.py").read_text(encoding="utf-8")
    assert 'READ_ONLY = "read-only"' not in source
    assert 'WORKSPACE_WRITE = "workspace-write"' not in source
    assert MODES is SANDBOX_MODES
    view = FilesystemView.for_local(tmp_path, access_mode="workspace-write")
    granted = writable_roots({"mode": "workspace-write", "workspace_root": str(tmp_path.resolve())})
    assert any(inside(root, Path(view.root_path("workspace"))) for root in granted)
    assert view.root_path and all(
        root.writable == (root.name != "package")
        for root in view.roots
        if root.name in {"workspace", "temp"}
    )
    readonly = view.with_access_mode("read-only")
    assert not any(root.writable for root in readonly.roots)


def test_file_door_blocks_escape_and_secrets(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    outside = tmp_path / "out"
    workspace.mkdir()
    outside.mkdir()
    door = FileDoor(FilesystemView.for_local(workspace, access_mode="workspace-write"))
    written = door.write_text("notes.txt", "inside")
    assert written.read_text(encoding="utf-8") == "inside"
    with pytest.raises(PermissionError):
        door.write_text(str(outside / "escape.txt"), "no")
    with pytest.raises(PermissionError):
        door.write_text(".env", "SECRET=1")
    link = workspace / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("this host cannot create a directory symlink")
    with pytest.raises(PermissionError):
        door.write_text("link/pwn.txt", "no")
    assert not (outside / "pwn.txt").exists()


def test_read_only_file_door_rejects_writes(tmp_path: Path) -> None:
    door = FileDoor(FilesystemView.for_local(tmp_path, access_mode="read-only"))
    with pytest.raises(PermissionError):
        door.write_text("notes.txt", "no")
    assert not (tmp_path / "notes.txt").exists()


def test_read_only_command_can_start_and_a_missing_runner_fails_closed(tmp_path: Path) -> None:
    room = _room(tmp_path, "read-only")
    original = (sys.executable, "-c", "print('ok')")
    permit = room.compute.prepare(original, cwd=str(tmp_path), timeout_seconds=10)
    assert permit.argv != original
    assert Path(permit.cwd) == tmp_path.resolve()
    try:
        completed, used = room.compute.run(original, cwd=str(tmp_path), timeout_seconds=10)
    except RuntimeError as exc:
        assert "unavailable" in str(exc)
        return
    assert completed.returncode == 0
    assert "ok" in completed.stdout
    assert used.enforcement in {"full", "partial"}


def test_danger_full_access_is_not_wrapped(tmp_path: Path) -> None:
    room = _room(tmp_path, "danger-full-access", confine=False)
    permit = room.compute.prepare((sys.executable, "-c", "print(1)"), cwd=str(tmp_path), timeout_seconds=5)
    assert permit.argv[0] == sys.executable
    assert permit.enforcement is None


def test_a_confined_mode_without_an_isolator_is_refused(tmp_path: Path) -> None:
    room = _room(tmp_path, "read-only", confine=False)
    with pytest.raises(RuntimeError, match="No isolator"):
        room.compute.prepare(("python", "-c", "print(1)"), cwd=str(tmp_path), timeout_seconds=5)
