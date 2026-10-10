"""Who this process is, and which secret names it may resolve."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from typing import Any, Mapping


SENSITIVE_NAME = re.compile(r"KEY|PASSWORD|SECRET|TOKEN", re.IGNORECASE)
ACCESS_MODES = ("read-only", "workspace-write")
_WIDER = {"read-only": "workspace-write"}


def sensitive_name(name: str) -> bool:
    """True when a variable name looks like a secret."""
    return bool(SENSITIVE_NAME.search(name))


def check_access_mode(mode: str) -> str:
    if mode not in ACCESS_MODES:
        raise ValueError("文件模式只能是只读或只能改工作区")
    return mode


@dataclass(frozen=True)
class IdentityDoor:
    """Process identity. Secret values are read when used, never stored here."""

    process_id: str
    capability_id: str
    access_mode: str = "workspace-write"
    widened_once: bool = False

    def __post_init__(self) -> None:
        if not self.process_id.strip():
            raise ValueError("process_id must not be empty")
        if not self.capability_id.strip():
            raise ValueError("capability_id must not be empty")
        object.__setattr__(self, "access_mode", check_access_mode(self.access_mode))

    def resolve_secret(self, name: str) -> str:
        """Read one named secret from the process environment at use time."""
        if not name or "\x00" in name:
            raise ValueError("密钥名字无效")
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"环境里没有这个密钥: {name}")
        return value

    def scrub_env(self, source: Mapping[str, str] | None = None) -> dict[str, str]:
        """Drop secret-like names before an external program starts."""
        found = os.environ if source is None else source
        return {
            str(key): str(value)
            for key, value in found.items()
            if key and not sensitive_name(str(key))
        }

    def approve_wider(self, approver: str) -> "IdentityDoor":
        """Widen one step, once. A peer process cannot approve this."""
        if self.widened_once:
            raise ValueError("已经放宽过一次")
        nxt = _WIDER.get(self.access_mode)
        if nxt is None:
            raise ValueError("不能再放宽")
        if approver not in {"user", "policy"}:
            raise ValueError("只能由用户或策略放宽")
        return replace(self, access_mode=nxt, widened_once=True)

    def payload(self) -> dict[str, Any]:
        return {
            "process_id": self.process_id,
            "capability_id": self.capability_id,
            "access_mode": self.access_mode,
            "widened_once": self.widened_once,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "IdentityDoor":
        return cls(
            process_id=str(payload["process_id"]),
            capability_id=str(payload["capability_id"]),
            access_mode=str(payload.get("access_mode", "workspace-write")),
            widened_once=bool(payload.get("widened_once", False)),
        )
