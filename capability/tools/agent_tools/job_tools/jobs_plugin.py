# -*- coding: utf-8 -*-
"""Kind-agnostic background job controller: list, read, and kill."""

from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from typing import Any, Optional


PLUGIN_NAME = "jobs"
PLUGIN_VERSION = "1.0"

WAIT_TIMEOUT_MS = 30_000
MAX_WAIT_TIMEOUT_MS = 600_000
STATUSES = ("running", "stopping", "completed", "killed", "failed")

_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()


JOB_KILL_SCHEMA: dict[str, Any] = {
    "name": "job_kill",
    "description": (
        "Request cancellation of a running background job by job id. Returns "
        "immediately; the job settles as killed once its work actually stops."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "Job id returned by the tool that started the background work.",
            },
            "reason": {
                "type": "string",
                "description": "Optional short reason, recorded in the log and forwarded to the job.",
            },
        },
        "required": ["job_id"],
    },
}

JOB_LIST_SCHEMA: dict[str, Any] = {
    "name": "job_list",
    "description": "List your background jobs (running and finished) with their ids, kinds, and statuses.",
    "parameters": {"type": "object", "properties": {}},
}

JOB_OUTPUT_SCHEMA: dict[str, Any] = {
    "name": "job_output",
    "description": (
        "Read a background job. Stream jobs return only output since the previous "
        "read; final-output jobs return their result after settlement. Every "
        "response ends with `[status: ...]`. Reads are non-blocking unless "
        "`wait: true`."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "string",
                "description": "Job id returned by the tool that started the background work.",
            },
            "wait": {
                "type": "boolean",
                "description": (
                    "Block until the job reaches a terminal status or the timeout "
                    "expires. A timed-out wait returns [status: running] and leaves "
                    "the job alive."
                ),
            },
            "timeout_ms": {
                "type": "number",
                "description": "Max wait in milliseconds (only meaningful with wait: true).",
            },
        },
        "required": ["job_id"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [JOB_KILL_SCHEMA, JOB_LIST_SCHEMA, JOB_OUTPUT_SCHEMA]



def load(kind, body, call_params=None):
    """Load one tool call. The body names which tool this plugin runs."""
    if kind != "tool":
        raise ValueError(f"这个进程不能装入 {kind}")
    if not isinstance(body, dict) or "name" not in body:
        raise TypeError("tool 的内容必须带上 name")
    tool_name = str(body["name"])
    arguments = {key: value for key, value in body.items() if key != "name"}
    return dispatch(tool_name, arguments, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name == "job_kill":
        return job_kill(str(arguments.get("job_id") or ""), arguments.get("reason"), **kwargs)
    if name == "job_list":
        return job_list(**kwargs)
    if name == "job_output":
        return job_output(
            str(arguments.get("job_id") or ""),
            bool(arguments.get("wait")),
            arguments.get("timeout_ms"),
            **kwargs,
        )
    return _error(f"unknown tool: {name}")


def start_job(
    kind: str,
    label: str,
    argv: Optional[list[str]] = None,
    cwd: Optional[str] = None,
    owner: Optional[str] = None,
) -> dict[str, Any]:
    """Host/producer entry: register a background process job."""
    job_id = uuid.uuid4().hex[:12]
    record: dict[str, Any] = {
        "id": job_id,
        "kind": kind,
        "label": label,
        "status": "running",
        "startedAt": int(time.time() * 1000),
        "text": "",
        "cursor": 0,
        "owner": owner or "default",
        "process": None,
    }
    with _LOCK:
        _JOBS[job_id] = record
    if argv:
        thread = threading.Thread(
            target=_run_process,
            args=(record, argv, cwd),
            name=f"job-{job_id}",
            daemon=True,
        )
        thread.start()
    return _public(record)


def job_list(owner: Optional[str] = None) -> str:
    key = owner or "default"
    with _LOCK:
        rows = [_public(item) for item in _JOBS.values() if item.get("owner") == key]
    return json.dumps({"success": True, "jobs": rows}, ensure_ascii=False)


def job_kill(job_id: str, reason: Optional[str] = None, owner: Optional[str] = None) -> str:
    record = _get(job_id, owner)
    if record is None:
        return _error("unknown job_id")
    process = record.get("process")
    if record["status"] == "running" and process is not None:
        record["status"] = "stopping"
        try:
            process.terminate()
        except OSError:
            pass
    elif record["status"] == "running":
        record["status"] = "killed"
        record["finishedAt"] = int(time.time() * 1000)
    if reason:
        record["detail"] = str(reason)
    return json.dumps({"success": True, "job": _public(record)}, ensure_ascii=False)


def job_output(
    job_id: str,
    wait: bool = False,
    timeout_ms: Optional[float] = None,
    owner: Optional[str] = None,
) -> str:
    record = _get(job_id, owner)
    if record is None:
        return _error("unknown job_id")
    if wait and record["status"] == "running":
        budget = min(timeout_ms or WAIT_TIMEOUT_MS, MAX_WAIT_TIMEOUT_MS) / 1000.0
        deadline = time.time() + budget
        while record["status"] == "running" and time.time() < deadline:
            time.sleep(0.05)
    with _LOCK:
        text = record["text"][record["cursor"] :]
        record["cursor"] = len(record["text"])
        snapshot = _public(record)
    body = text if text else "(no new output)"
    rendered = f"{body.rstrip()}\n{_status_line(snapshot)}"
    return json.dumps(
        {"success": True, "text": rendered, "job": snapshot},
        ensure_ascii=False,
    )


def _run_process(record: dict[str, Any], argv: list[str], cwd: Optional[str]) -> None:
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        record["process"] = process
        out, _ = process.communicate()
        record["text"] = out or ""
        if record["status"] == "stopping":
            record["status"] = "killed"
        else:
            record["status"] = "completed" if process.returncode == 0 else "failed"
            record["detail"] = f"exit code {process.returncode}"
        record["finishedAt"] = int(time.time() * 1000)
    except Exception as exc:
        record["status"] = "failed"
        record["detail"] = str(exc)
        record["finishedAt"] = int(time.time() * 1000)


def _get(job_id: str, owner: Optional[str]) -> Optional[dict[str, Any]]:
    if not job_id:
        return None
    key = owner or "default"
    with _LOCK:
        record = _JOBS.get(job_id)
        if record is None or record.get("owner") != key:
            return None
        return record


def _public(record: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": record["id"],
        "kind": record["kind"],
        "label": record["label"],
        "status": record["status"],
        "startedAt": record["startedAt"],
    }
    if record.get("detail"):
        payload["detail"] = record["detail"]
    if record.get("finishedAt"):
        payload["finishedAt"] = record["finishedAt"]
    return payload


def _status_line(snapshot: dict[str, Any]) -> str:
    if snapshot.get("detail"):
        return f"[status: {snapshot['status']}, {snapshot['detail']}]"
    return f"[status: {snapshot['status']}]"


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

