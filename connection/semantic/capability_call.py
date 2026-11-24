"""Validate a desktop capability call and turn it into kernel command lines.

The second command needs the pid from ``process start``, so the gateway sends
these lines itself. This module only checks the allowlist and builds the text.
"""

from __future__ import annotations

import json
import shlex
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from connection.protocol.request import ProtocolError
from connection.semantic.validators import optional_text, required_text


ALLOWED_CAPABILITIES = frozenset(
    {
        "tools.list_dir",
        "tools.read",
        "tools.write",
        "tools.grep",
        "tools.read_image",
        "tools.terminal_desktop",
        "tools.run_code",
        "tools.ddgs",
        "tools.brave_free",
        "tools.exa",
        "tools.tavily",
        "tools.firecrawl",
        "tools.parallel",
        "tools.searxng",
        "tools.mcp_tool_manager",
        "sandbox.sandbox",
    }
)

_FIELDS = frozenset({"capability", "kind", "body", "hold", "cwd"})


@dataclass(frozen=True)
class CapabilityCall:
    """One desktop request that starts or reuses a capability process."""

    capability: str
    kind: str
    body: dict[str, Any]
    hold: bool
    cwd: str


def prepare_capability_call(payload: Mapping[str, Any]) -> CapabilityCall:
    """Reject anything outside the desktop allowlist."""

    unknown = set(payload) - _FIELDS
    if unknown:
        raise ProtocolError(
            "invalid_payload",
            f"Unknown capability.call fields: {sorted(unknown)}",
        )
    capability = required_text(payload, "capability")
    if capability not in ALLOWED_CAPABILITIES:
        raise ProtocolError(
            "unsupported_capability",
            f"Unsupported capability: {capability}",
        )
    kind = required_text(payload, "kind")
    expected = "sandbox" if capability == "sandbox.sandbox" else "tool"
    if kind != expected:
        raise ProtocolError("invalid_payload", f"{capability} uses kind {expected}")
    body = payload.get("body", {})
    if not isinstance(body, dict):
        raise ProtocolError("invalid_payload", "body must be an object")
    hold = _hold(payload)
    cwd = optional_text(payload, "cwd") or ""
    return CapabilityCall(
        capability=capability,
        kind=kind,
        body=dict(body),
        hold=hold,
        cwd=cwd,
    )


def start_command(spec: CapabilityCall) -> str:
    """Open the capability. A held process stays up for the next call."""

    parts = ["process", "start", spec.capability]
    if spec.cwd:
        parts.extend(["--cwd", spec.cwd])
    if not spec.hold:
        parts.append("--once")
    return shlex.join(parts)


def load_command(spec: CapabilityCall, pid: int) -> str:
    """Hand the body to a process that is already open."""

    head = shlex.join(["load", spec.kind, str(pid)])
    return f"{head} -- {json.dumps(spec.body, ensure_ascii=False)}"


def started_pid(value: Any) -> int | None:
    """Read the pid ``process start`` puts in its completed value."""

    if not isinstance(value, dict):
        return None
    processes = value.get("processes")
    if not isinstance(processes, list) or not processes:
        return None
    first = processes[0]
    if not isinstance(first, dict):
        return None
    pid = first.get("pid")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid < 1:
        return None
    return pid


def _hold(payload: Mapping[str, Any]) -> bool:
    value = payload.get("hold", False)
    if not isinstance(value, bool):
        raise ProtocolError("invalid_payload", "hold must be a boolean")
    return value
