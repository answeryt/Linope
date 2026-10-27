# -*- coding: utf-8 -*-
"""edit and create go through the file door."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

from kernel.environment import (
    HostExecutionPolicy,
    KernelEnvironment,
    ProcessEnvironment,
    using_room,
)


def _load(name: str):
    path = Path(__file__).resolve().parents[1] / f"{name}_plugin.py"
    spec = importlib.util.spec_from_file_location(f"{name}_plugin_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _room(path: Path, mode: str):
    shell = ProcessEnvironment.current(pid=os.getpid(), capability_id="tools.edit", cwd=path)
    return KernelEnvironment.build(
        shell=shell,
        policy=HostExecutionPolicy(),
        max_concurrent_tasks=1,
        max_sync_workers=1,
        access_mode=mode,
        confine=False,
    )


class EditPluginTest(unittest.TestCase):
    def test_read_only_room_cannot_edit_or_create(self) -> None:
        edit = _load("edit")
        editor = _load("str_replace_editor")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "notes.txt"
            target.write_text("alpha", encoding="utf-8")
            with using_room(_room(root, "read-only")):
                edited = json.loads(
                    edit.dispatch(
                        "edit",
                        {
                            "file_path": "notes.txt",
                            "old_string": "alpha",
                            "new_string": "beta",
                        },
                        workspace=directory,
                    )
                )
                created = json.loads(
                    editor.dispatch(
                        "str_replace_editor",
                        {"command": "create", "path": "new.txt", "file_text": "new"},
                        workspace=directory,
                    )
                )
            self.assertFalse(edited["success"], edited)
            self.assertEqual(target.read_text(encoding="utf-8"), "alpha")
            self.assertFalse(created["success"], created)
            self.assertFalse((root / "new.txt").exists())

    def test_create_does_not_overwrite(self) -> None:
        editor = _load("str_replace_editor")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "notes.txt"
            target.write_text("keep", encoding="utf-8")
            with using_room(_room(root, "workspace-write")):
                payload = json.loads(
                    editor.dispatch(
                        "str_replace_editor",
                        {"command": "create", "path": "notes.txt", "file_text": "replace"},
                        workspace=directory,
                    )
                )
            self.assertFalse(payload["success"], payload)
            self.assertEqual(target.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
