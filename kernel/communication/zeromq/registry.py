"""Channel-owned ZeroMQ endpoint and reply registry.

The registry deliberately lives outside the general resource ledger. Endpoint
discovery must not open, reap, or rewrite the ledger while a capability process
is becoming ready.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


def _root(store_path: str) -> Path:
    raw = str(store_path or "")
    if raw.startswith("file:"):
        raw = raw[5:]
    candidate = Path(raw).expanduser()
    if raw and not raw.startswith(("sqlite:", "postgresql:", "mysql:")):
        return candidate.with_name(candidate.name + ".zeromq")
    digest = hashlib.sha256(str(store_path).encode("utf-8")).hexdigest()[:20]
    return Path(tempfile.gettempdir()) / "linope-zeromq" / digest


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def publish_endpoint(
    store_path: str,
    process_id: str,
    endpoint: str,
) -> str:
    generation = uuid.uuid4().hex
    _write_json(
        _root(store_path) / "endpoints" / f"{process_id}.json",
        {
            "process_id": process_id,
            "endpoint": endpoint,
            "generation": generation,
            "pid": os.getpid(),
            "updated_at": time.time(),
        },
    )
    return generation


def endpoint_for(store_path: str, process_id: str) -> dict[str, Any] | None:
    path = _root(store_path) / "endpoints" / f"{process_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not payload.get("endpoint"):
        return None
    return payload


def remove_endpoint(store_path: str, process_id: str, generation: str) -> None:
    path = _root(store_path) / "endpoints" / f"{process_id}.json"
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(current, dict) and current.get("generation") == generation:
        try:
            path.unlink()
        except OSError:
            pass


def publish_reply(store_path: str, request_id: str, reply: dict[str, Any]) -> None:
    _write_json(
        _root(store_path) / "replies" / f"{request_id}.json",
        {"request_id": request_id, "reply": reply, "updated_at": time.time()},
    )


def reply_for(store_path: str, request_id: str) -> dict[str, Any] | None:
    path = _root(store_path) / "replies" / f"{request_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    reply = payload.get("reply") if isinstance(payload, dict) else None
    return reply if isinstance(reply, dict) else None
