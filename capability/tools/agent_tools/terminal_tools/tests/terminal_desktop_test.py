# -*- coding: utf-8 -*-
"""A held PowerShell session can take one line and give it back."""

from __future__ import annotations

import importlib.util
import json
import shutil
import time
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "terminal_desktop_plugin.py"
    spec = importlib.util.spec_from_file_location("terminal_desktop_plugin_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(
    any(shutil.which(name) for name in ("pwsh", "powershell", "powershell.exe")),
    "PowerShell is not installed",
)
class TerminalDesktopPluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.plugin = _load()

    def test_open_send_read_and_close(self) -> None:
        opened = json.loads(self.plugin.dispatch("terminal_desktop", {"action": "open", "name": "main"}))
        self.assertTrue(opened["success"], opened)
        session_id = opened["sessionId"]
        try:
            sent = json.loads(
                self.plugin.dispatch(
                    "terminal_desktop",
                    {"action": "send", "sessionId": session_id, "text": "Write-Output linope-desktop-ok"},
                )
            )
            self.assertTrue(sent["success"], sent)
            text = ""
            deadline = time.time() + 15
            while time.time() < deadline:
                read = json.loads(
                    self.plugin.dispatch("terminal_desktop", {"action": "read", "sessionId": session_id})
                )
                self.assertTrue(read["success"], read)
                text = str(read["text"])
                if "linope-desktop-ok" in text:
                    break
                time.sleep(0.2)
            self.assertIn("linope-desktop-ok", text)
        finally:
            closed = json.loads(
                self.plugin.dispatch("terminal_desktop", {"action": "close", "sessionId": session_id})
            )
            self.assertTrue(closed["success"], closed)


if __name__ == "__main__":
    unittest.main()
