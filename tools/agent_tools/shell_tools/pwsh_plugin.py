# -*- coding: utf-8 -*-
"""One-shot PowerShell tool. Each call starts a fresh `pwsh -Command` process."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any, Optional


PLUGIN_NAME = "pwsh"
PLUGIN_VERSION = "1.0"

DEFAULT_TIMEOUT_MS = 60_000
MAX_INLINE_CHARS = 100_000
JobsStart = Callable[..., dict[str, Any]]

_BACKGROUND: dict[str, dict[str, Any]] = {}
_BACKGROUND_LOCK = threading.Lock()


PWSH_SCHEMA: dict[str, Any] = {
    "name": "pwsh",
    "description": (
        "Execute a PowerShell command (`pwsh -Command`) and return its stdout/stderr. "
        "Each call runs in a fresh pwsh process: no state persists between calls — "
        "pass `workdir` instead of using `cd`. Paths use native Windows form (`C:\\...`); "
        "read environment variables with `$env:NAME`. Non-zero exits are reported as "
        "`[exit code: N]`. Set `run_in_background: true` for long-running commands."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The PowerShell command to execute.",
            },
            "description": {
                "type": "string",
                "description": (
                    "Clear, concise description of what this command does in "
                    "active voice, 5-10 words (shown in the UI)."
                ),
            },
            "timeoutMs": {
                "type": "number",
                "description": (
                    "Timeout in milliseconds. The executor applies its "
                    "configured default and cap, and kills the command on expiry."
                ),
            },
            "workdir": {
                "type": "string",
                "description": (
                    "Working directory for this command. Defaults to the "
                    "session workspace; a relative path is resolved against it."
                ),
            },
            "run_in_background": {
                "type": "boolean",
                "description": (
                    "Run in the background and return a job id immediately "
                    "(collect with job_output, stop with job_kill). No timeout applies."
                ),
            },
        },
        "required": ["command", "description"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [PWSH_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "pwsh":
        return _error(f"unknown tool: {name}")
    return pwsh(
        command=str(arguments.get("command") or ""),
        description=str(arguments.get("description") or ""),
        timeout_ms=arguments.get("timeoutMs"),
        workdir=arguments.get("workdir"),
        run_in_background=bool(arguments.get("run_in_background")),
        **kwargs,
    )


def pwsh(
    command: str,
    description: str,
    timeout_ms: Optional[float] = None,
    workdir: Optional[str] = None,
    run_in_background: bool = False,
    jobs_start: Optional[JobsStart] = None,
    workspace: Optional[str] = None,
) -> str:
    """Run `command` in a fresh PowerShell process."""
    if not command.strip():
        return _error("invalid command: expected a non-empty string")
    if not description.strip():
        return _error("invalid description: expected a non-empty string")
    if timeout_ms is not None and (not isinstance(timeout_ms, (int, float)) or timeout_ms <= 0):
        return _error(f"invalid timeoutMs: expected a positive number, got {timeout_ms!r}")

    cwd = _resolve_workdir(workdir, workspace)
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        return _error("pwsh/powershell is not available on this host")

    argv = [executable, "-NoProfile", "-NonInteractive", "-Command", command]
    if run_in_background:
        return _start_background(argv, cwd, description, jobs_start)

    timeout = (timeout_ms or DEFAULT_TIMEOUT_MS) / 1000.0
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return _error(f"command timed out after {int(timeout * 1000)}ms")
    except OSError as exc:
        return _error(str(exc))

    text = "".join(part for part in (completed.stdout, completed.stderr) if part)
    if len(text) > MAX_INLINE_CHARS:
        text = text[-MAX_INLINE_CHARS:]
    if completed.returncode != 0:
        marker = f"[exit code: {completed.returncode}]"
        text = f"{text.rstrip()}\n{marker}" if text.strip() else marker
    return json.dumps({"success": True, "text": text, "exitCode": completed.returncode}, ensure_ascii=False)


def _start_background(
    argv: list[str],
    cwd: str,
    label: str,
    jobs_start: Optional[JobsStart],
) -> str:
    if jobs_start is not None:
        snapshot = jobs_start(kind="pwsh", label=label, argv=argv, cwd=cwd)
        return json.dumps({"success": True, "job": snapshot}, ensure_ascii=False)

    job_id = uuid.uuid4().hex[:12]
    record: dict[str, Any] = {
        "id": job_id,
        "kind": "pwsh",
        "label": label,
        "status": "running",
        "startedAt": int(time.time() * 1000),
        "text": "",
    }
    with _BACKGROUND_LOCK:
        _BACKGROUND[job_id] = record

    def _worker() -> None:
        try:
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            out, _ = proc.communicate()
            record["text"] = out or ""
            record["status"] = "completed" if proc.returncode == 0 else "failed"
            record["detail"] = f"exit code {proc.returncode}"
            record["finishedAt"] = int(time.time() * 1000)
        except Exception as exc:
            record["status"] = "failed"
            record["detail"] = str(exc)
            record["finishedAt"] = int(time.time() * 1000)

    threading.Thread(target=_worker, name=f"pwsh-job-{job_id}", daemon=True).start()
    return json.dumps(
        {
            "success": True,
            "job": {
                "id": job_id,
                "kind": "pwsh",
                "label": label,
                "status": "running",
                "startedAt": record["startedAt"],
            },
        },
        ensure_ascii=False,
    )


def _resolve_workdir(workdir: Optional[str], workspace: Optional[str]) -> str:
    root = workspace or os.getenv("TERMINAL_CWD") or os.getcwd()
    if not workdir:
        return os.path.abspath(root)
    if os.path.isabs(workdir):
        return os.path.abspath(workdir)
    return os.path.abspath(os.path.join(root, workdir))


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
