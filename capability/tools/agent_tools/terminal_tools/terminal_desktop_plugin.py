# -*- coding: utf-8 -*-
"""One held process that keeps PowerShell sessions for the desktop terminal."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Optional


PLUGIN_NAME = "terminal_desktop"
PLUGIN_VERSION = "1.0"

_BUFFER_LIMIT = 80_000
_DONE = "__LINOPE_DONE__"
_EXECUTABLE_NAMES = ("pwsh", "powershell", "powershell.exe")
_LOOP = """[Console]::Out.WriteLine('__LINOPE_READY__')
[Console]::Out.Flush()
$reader = New-Object System.IO.StreamReader([Console]::OpenStandardInput())
while ($null -ne ($line = $reader.ReadLine())) {
  if ($line -eq '__LINOPE_EXIT__') { break }
  try {
    $result = Invoke-Expression $line | Out-String
    if ($result) { [Console]::Out.WriteLine($result.TrimEnd()) }
  } catch {
    [Console]::Out.WriteLine($_.Exception.Message)
  }
  [Console]::Out.WriteLine('__LINOPE_DONE__')
  [Console]::Out.Flush()
}
"""
_SESSIONS: dict[str, "_Session"] = {}
_LOCK = threading.Lock()

TERMINAL_DESKTOP_SCHEMA: dict[str, Any] = {
    "name": "terminal_desktop",
    "description": (
        "Open, write, read, interrupt, and close persistent PowerShell sessions "
        "owned by this process. Full-screen programs are not supported."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["open", "send", "read", "list", "close", "signal"],
                "description": "What to do with the desktop terminal sessions.",
            },
            "sessionId": {
                "type": "string",
                "description": "Session id returned by open or list.",
            },
            "text": {
                "type": "string",
                "description": "One line to send. Used by send.",
            },
            "name": {
                "type": "string",
                "description": "Display name for a new session.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for a new session.",
            },
        },
        "required": ["action"],
    },
}


class _Session:
    def __init__(
        self,
        session_id: str,
        name: str,
        cwd: str,
        proc: subprocess.Popen[bytes],
        script: Path,
    ) -> None:
        self.id = session_id
        self.name = name
        self.cwd = cwd
        self.proc = proc
        self.script = script
        self.buffer = ""
        self.pending = b""
        self.encoding: Optional[str] = None
        self.lock = threading.Lock()
        self.reader = threading.Thread(target=_read_output, args=(self,), name=f"terminal-{session_id}", daemon=True)
        self.reader.start()

    def alive(self) -> bool:
        return self.proc.poll() is None


def tool_schemas() -> list[dict[str, Any]]:
    return [TERMINAL_DESKTOP_SCHEMA]


def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    del call_params
    if kind != "tool":
        raise ValueError(f"This process cannot load {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool content must be a mapping")
    return dispatch("terminal_desktop", body)


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    del kwargs
    if name != "terminal_desktop":
        return _error(f"unknown tool: {name}")
    action = str(arguments.get("action") or "").strip()
    if action == "open":
        return _open(arguments.get("name"), arguments.get("cwd"))
    if action == "send":
        return _send(str(arguments.get("sessionId") or ""), arguments.get("text"))
    if action == "read":
        return _read(str(arguments.get("sessionId") or ""))
    if action == "list":
        return _list()
    if action == "close":
        return _close(str(arguments.get("sessionId") or ""))
    if action == "signal":
        return _interrupt(str(arguments.get("sessionId") or ""))
    return _error("action must be open, send, read, list, close, or signal")


def _open(name: Any, cwd: Any) -> str:
    executable = _executable()
    if executable is None:
        return _error("PowerShell was not found")
    folder = str(cwd or "").strip()
    if folder and not Path(folder).is_dir():
        return _error(f"directory not found: {folder}")
    label = str(name or "").strip() or "终端"
    script = _script_file()
    command = [
        executable,
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
    ]
    kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "cwd": folder or None,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        kwargs["start_new_session"] = True
    try:
        proc = subprocess.Popen(command, **kwargs)
    except OSError as error:
        try:
            script.unlink(missing_ok=True)
        except OSError:
            pass
        return _error(str(error))
    session_id = uuid.uuid4().hex[:8]
    session = _Session(session_id, label, folder, proc, script)
    with _LOCK:
        _SESSIONS[session_id] = session
    return json.dumps(
        {"success": True, "sessionId": session_id, "name": label, "cwd": folder},
        ensure_ascii=False,
    )


def _send(session_id: str, text: Any) -> str:
    session = _session(session_id)
    if isinstance(session, str):
        return session
    if not session.alive() or session.proc.stdin is None:
        return _error("this terminal is closed")
    line = "" if text is None else str(text)
    line = line.replace("\r\n", "\n").replace("\r", "\n").split("\n", 1)[0]
    try:
        session.proc.stdin.write((line + "\n").encode("utf-8"))
        session.proc.stdin.flush()
    except OSError as error:
        return _error(str(error))
    return json.dumps({"success": True, "sessionId": session.id}, ensure_ascii=False)


def _read(session_id: str) -> str:
    session = _session(session_id)
    if isinstance(session, str):
        return session
    with session.lock:
        text = session.buffer.replace("__LINOPE_READY__\r\n", "").replace("__LINOPE_READY__\n", "")
        text = text.replace(f"{_DONE}\r\n", "").replace(f"{_DONE}\n", "")
    return json.dumps(
        {
            "success": True,
            "sessionId": session.id,
            "text": text,
            "alive": session.alive(),
        },
        ensure_ascii=False,
    )


def _list() -> str:
    with _LOCK:
        rows = [
            {"sessionId": item.id, "name": item.name, "cwd": item.cwd, "alive": item.alive()}
            for item in _SESSIONS.values()
        ]
    return json.dumps({"success": True, "sessions": rows}, ensure_ascii=False)


def _close(session_id: str) -> str:
    session = _take(session_id)
    if isinstance(session, str):
        return session
    _stop(session)
    return json.dumps({"success": True, "sessionId": session_id}, ensure_ascii=False)


def _interrupt(session_id: str) -> str:
    session = _session(session_id)
    if isinstance(session, str):
        return session
    if not session.alive():
        return _error("this terminal is closed")
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(session.proc.pid)],
                capture_output=True,
                check=False,
            )
        else:
            os.killpg(session.proc.pid, signal.SIGINT)
    except (OSError, ProcessLookupError) as error:
        return _error(str(error))
    return json.dumps({"success": True, "sessionId": session.id}, ensure_ascii=False)


def _read_output(session: _Session) -> None:
    stream = session.proc.stdout
    if stream is None:
        return
    while True:
        try:
            chunk = os.read(stream.fileno(), 4096)
        except OSError:
            break
        if not chunk:
            break
        session.pending += chunk
        if session.encoding is None and len(session.pending) >= 2:
            session.encoding = "utf-16-le" if b"\x00" in session.pending[:8] else "utf-8"
        if session.encoding is None:
            continue
        pending = session.pending
        if session.encoding == "utf-16-le" and len(pending) % 2:
            session.pending = pending[-1:]
            pending = pending[:-1]
        else:
            session.pending = b""
        if not pending:
            continue
        text = pending.decode(session.encoding, errors="replace")
        with session.lock:
            session.buffer = (session.buffer + text)[-_BUFFER_LIMIT:]


def _session(session_id: str) -> _Session | str:
    if not session_id.strip():
        return _error("sessionId is required")
    with _LOCK:
        found = _SESSIONS.get(session_id)
    if found is None:
        return _error("terminal session was not found")
    return found


def _take(session_id: str) -> _Session | str:
    if not session_id.strip():
        return _error("sessionId is required")
    with _LOCK:
        found = _SESSIONS.pop(session_id, None)
    if found is None:
        return _error("terminal session was not found")
    return found


def _stop(session: _Session) -> None:
    if session.proc.poll() is None:
        session.proc.kill()
    try:
        session.proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    try:
        session.script.unlink(missing_ok=True)
    except OSError:
        pass


def _script_file() -> Path:
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".ps1", delete=False)
    try:
        handle.write(_LOOP)
    finally:
        handle.close()
    return Path(handle.name)


def _executable() -> str | None:
    for name in _EXECUTABLE_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)


def capability_profile(capability_id, changes):
    """This process leases a tool and the shared project workspace."""
    from capability.tools.profile import workspace_tool

    return workspace_tool(capability_id, changes, "workspace-write")
