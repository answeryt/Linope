# -*- coding: utf-8 -*-
"""Owner-isolated persistent bash. State survives across calls for one agent."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "bash_persistent"
PLUGIN_VERSION = "1.0"

DEFAULT_TIMEOUT_MS = 300_000
PersistRunner = Callable[..., dict[str, Any]]

_SESSIONS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


BASH_PERSISTENT_SCHEMA: dict[str, Any] = {
    "name": "bash",
    "description": (
        "Run commands in a persistent bash shell. State, including the current "
        "directory and exported environment variables, persists across calls "
        "for this agent."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to run. Relative path is preferred in the command.",
            },
        },
        "required": ["command"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [BASH_PERSISTENT_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if isinstance(body, str):
        body = {"command": body, "description": body}
    if not isinstance(body, dict):
        raise TypeError("tool 的内容必须是映射")
    return dispatch("bash", body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "bash":
        return _error(f"unknown tool: {name}")
    return bash_persistent(command=str(arguments.get("command") or ""), **kwargs)


def bash_persistent(
    command: str,
    owner: Optional[str] = None,
    timeout_ms: Optional[float] = None,
    workspace: Optional[str] = None,
    persist: Optional[PersistRunner] = None,
) -> str:
    """Run `command` in the owner's persistent bash session."""
    if not command.strip():
        return _error("invalid command: expected a non-empty string")
    if persist is not None:
        result = persist(command=command, owner=owner or "default")
        return json.dumps({"success": True, **result}, ensure_ascii=False)

    executable = shutil.which("bash")
    if executable is None:
        return _error("bash is not available on this host")

    key = owner or "default"
    timeout = (timeout_ms or DEFAULT_TIMEOUT_MS) / 1000.0
    with _LOCK:
        session = _SESSIONS.get(key)
        if session is None:
            session = {
                "cwd": os.path.abspath(workspace or os.getenv("TERMINAL_CWD") or os.getcwd()),
                "env": os.environ.copy(),
            }
            _SESSIONS[key] = session

    wrapper = (
        "{ " + command + "; }; __dsh_status=$?\n"
        'printf "\\n__DSH_CWD__:%s\\n" "$(pwd -P)"\n'
        "exit $__dsh_status"
    )
    try:
        completed = subprocess.run(
            [executable, "-lc", wrapper],
            cwd=session["cwd"],
            env=session["env"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return _error(f"command timed out after {int(timeout * 1000)}ms")
    except OSError as exc:
        return _error(str(exc))

    stdout = completed.stdout or ""
    marker = "\n__DSH_CWD__:"
    if marker in stdout:
        stdout, suffix = stdout.rsplit(marker, 1)
        candidate = suffix.splitlines()[0].strip() if suffix.strip() else ""
        if candidate and os.path.isdir(candidate):
            session["cwd"] = candidate

    text = "".join(part for part in (stdout, completed.stderr) if part)
    if completed.returncode != 0:
        marker = f"[exit code: {completed.returncode}]"
        text = f"{text.rstrip()}\n{marker}" if text.strip() else marker
    return json.dumps(
        {
            "success": True,
            "text": text,
            "exitCode": completed.returncode,
            "cwd": session["cwd"],
        },
        ensure_ascii=False,
    )


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)

def capability_profile(capability_id, changes):
    """Tell the process this tool needs a tool resource."""
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
        ),
    )

