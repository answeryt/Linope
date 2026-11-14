"""Shared prompt, tool schema, tasks, and utilization math."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE / "prompt.txt"
TOOLS_PATH = HERE / "tools.json"
FIXTURES = HERE / "fixtures"
RUNS = HERE / "runs"


def prompt_text() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def tool_schema() -> list[dict[str, Any]]:
    payload = json.loads(TOOLS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError("tools.json must contain one tool")
    return payload


def openai_tools(schema: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The tool list both arms send to the model."""

    return [
        {
            "type": "function",
            "function": {
                "name": item["name"],
                "description": item["description"],
                "parameters": item["parameters"],
            },
        }
        for item in (schema if schema is not None else tool_schema())
    ]


def fingerprint() -> dict[str, str]:
    """Hashes of the files both arms must read unchanged."""

    return {
        "prompt": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest(),
        "tools": hashlib.sha256(TOOLS_PATH.read_bytes()).hexdigest(),
    }


def task_text(task_id: str, path: Path, seconds: float, nonce: str) -> str:
    return (
        f"task: {task_id}\n"
        "Read the file.\n"
        f"Call wait_read exactly once with path {path} and seconds {seconds}.\n"
        f"nonce: {nonce}"
    )


def mechanism_tasks(seconds: float, nonce: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "a",
            "path": FIXTURES / "a.txt",
            "seconds": seconds,
            "text": task_text("a", FIXTURES / "a.txt", seconds, nonce),
        },
        {
            "id": "b",
            "path": FIXTURES / "b.txt",
            "seconds": seconds,
            "text": task_text("b", FIXTURES / "b.txt", seconds, nonce),
        },
    ]


def real_tasks(nonce: str) -> list[dict[str, Any]]:
    """One fast directory lookup and one fast file read. Their waits are natural."""

    folder = FIXTURES / "notes"
    note = folder / "readme.txt"
    return [
        {"id": "find", "path": folder, "seconds": 0, "text": task_text("find", folder, 0, nonce)},
        {"id": "note", "path": note, "seconds": 0, "text": task_text("note", note, 0, nonce)},
    ]


def tasks_for(group: str, seconds: float, nonce: str) -> list[dict[str, Any]]:
    if group == "mechanism":
        return mechanism_tasks(seconds, nonce)
    if group == "real":
        return real_tasks(nonce)
    raise ValueError("group must be mechanism or real")


def wait_seconds(samples: list[float], factor: float = 1.75) -> float:
    """Controlled wait from the high end of observed model-request times.

    The wait has to cover another full model request. A fixed floor such as
    15 seconds is only right when the model itself is that slow.
    """

    if not samples or any(item <= 0 for item in samples):
        raise ValueError("calibration needs positive request durations")
    if factor <= 1:
        raise ValueError("the wait must be longer than one model request")
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, math.ceil(0.9 * len(ordered)) - 1))
    return ordered[index] * factor


def append_event(path: Path, event: dict[str, Any]) -> None:
    """Append one JSON object. Safe across the proxy process and the runner."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    line = json.dumps(event, ensure_ascii=False) + "\n"
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except (FileExistsError, PermissionError):
            time.sleep(0.01)
            continue
        os.close(fd)
        break
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    finally:
        lock.unlink(missing_ok=True)


def load_events(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def request_intervals(events: list[dict[str, Any]]) -> list[tuple[float, float, str]]:
    pending: dict[str, tuple[float, str]] = {}
    spans: list[tuple[float, float, str]] = []
    for event in events:
        kind = event.get("kind")
        ident = str(event.get("id") or "")
        if kind == "request_start":
            pending[ident] = (float(event["t"]), str(event.get("task") or ""))
        elif kind == "request_end" and ident in pending:
            start, task = pending.pop(ident)
            spans.append((start, float(event["t"]), task))
    spans.sort()
    return spans


def requests_overlap(spans: list[tuple[float, float, str]]) -> bool:
    for earlier, later in zip(spans, spans[1:]):
        if later[0] < earlier[1]:
            return True
    return False


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    """U = Tbusy / Twall. Overlapping requests make the round unusable."""

    submitted = next(float(item["t"]) for item in events if item.get("kind") == "tasks_submitted")
    finished = [float(item["t"]) for item in events if item.get("kind") == "task_finished"]
    if len(finished) < 2:
        raise ValueError("both tasks must finish")
    wall_end = max(finished)
    twall = wall_end - submitted
    spans = request_intervals(events)
    overlap = requests_overlap(spans)
    tbusy = sum(end - start for start, end, _task in spans)
    counts: dict[str, int] = {}
    for _start, _end, task in spans:
        counts[task] = counts.get(task, 0) + 1
    trajectory_ok = counts == {"a": 2, "b": 2} or counts == {"find": 2, "note": 2}
    valid = twall > 0 and not overlap and trajectory_ok and len(spans) == 4
    return {
        "arm": next((item.get("arm") for item in events if item.get("kind") == "round"), ""),
        "group": next((item.get("group") for item in events if item.get("kind") == "round"), ""),
        "twall": twall,
        "tbusy": tbusy,
        "idle": twall - tbusy,
        "u": tbusy / twall if twall else 0,
        "valid": valid,
        "overlap": overlap,
        "trajectory_ok": trajectory_ok,
        "requests": len(spans),
    }
