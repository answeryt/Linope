# -*- coding: utf-8 -*-
"""Portable continuation intents whose readiness is an injected expression."""

from __future__ import annotations

import hashlib
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable


def _expression() -> Any:
    """Load the sibling expression plugin without requiring a Python package."""
    cached = getattr(_expression, "_module", None)
    if cached is not None:
        return cached
    import importlib.util
    from pathlib import Path

    path = Path(__file__).with_name("expression_plugin.py")
    spec = importlib.util.spec_from_file_location(
        "kernel_process_expression_lib", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load continuation expression plugin")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _expression._module = module
    return module


PLUGIN_NAME = "kernel_process_continuation"
PLUGIN_VERSION = "1.0"

Clock = Callable[[], float]


def _now(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _continuation_id(
    process_id: str, run_id: str, execution_id: str, sequence: int
) -> str:
    material = f"{process_id}\0{run_id}\0{execution_id}\0{sequence}".encode()
    return "continuation_" + hashlib.sha256(material).hexdigest()[:32]


def build_continuation(
    process_id: str,
    run_id: str,
    execution_id: str,
    *,
    sequence: int,
    reason: str | None = None,
    input: Any = None,
    when: Any = None,
    priority: int = 0,
    continuation_id: str | None = None,
    clock: Clock = time.time,
) -> dict[str, Any]:
    """Build a deterministic request for a future Process execution."""
    if not process_id or not run_id or not execution_id:
        raise ValueError("process_id, run_id, and execution_id are required")
    index = int(sequence)
    if index < 0:
        raise ValueError("sequence must be non-negative")
    timestamp = float(clock())
    record = {
        "type": "continuation",
        "continuation_id": continuation_id
        or _continuation_id(str(process_id), str(run_id), str(execution_id), index),
        "process_id": str(process_id),
        "run_id": str(run_id),
        "source_execution_id": str(execution_id),
        "sequence": index,
        "reason": None if reason is None else str(reason),
        "input": deepcopy(input),
        "when": _expression().normalize_expression(when),
        "priority": int(priority),
        "status": "pending",
        "created_at": _now(timestamp),
        "created_at_ts": timestamp,
        "facts": {"events": [], "latches": {}},
        "dispatched_at": None,
        "consumed_at": None,
    }
    return record
