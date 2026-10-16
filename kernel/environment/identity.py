"""Who this process is, and which secret names it may resolve."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping


from kernel.resource.workspace.mount.mode import MODES, check_mode

SENSITIVE_NAME = re.compile(r"KEY|PASSWORD|SECRET|TOKEN", re.IGNORECASE)
ACCESS_MODES = MODES
_WIDER = {"read-only": "workspace-write"}


def sensitive_name(name: str) -> bool:
    """True when a variable name looks like a secret."""
    return bool(SENSITIVE_NAME.search(name))


def check_access_mode(mode: str) -> str:
    return check_mode(mode)


@dataclass(frozen=True)
class IdentityDoor:
    """Process identity. Secret values stay in the env file and are read when used."""

    process_id: str
    capability_id: str
    access_mode: str = "workspace-write"
    widened_once: bool = False
    secret_file: str = ""
    secret_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.process_id.strip():
            raise ValueError("process_id must not be empty")
        if not self.capability_id.strip():
            raise ValueError("capability_id must not be empty")
        object.__setattr__(self, "access_mode", check_access_mode(self.access_mode))
        object.__setattr__(self, "secret_names", tuple(self.secret_names))

    def with_secrets(self, secret_file: str, secret_names: tuple[str, ...]) -> "IdentityDoor":
        """Remember where named secrets live. The values stay in the file."""
        return replace(self, secret_file=secret_file, secret_names=tuple(secret_names))

    def resolve_secret(self, name: str) -> str:
        """Read one named secret from the env file at use time."""
        if not name or "\x00" in name:
            raise ValueError("密钥名字无效")
        if name not in self.secret_names:
            raise RuntimeError(f"环境里没有这个密钥: {name}")
        return _read_named_secret(self.secret_file, name)

    def scrub_env(self, source: Mapping[str, str] | None = None) -> dict[str, str]:
        """Drop secret-like names, and this process's named secrets, before an external program starts."""
        found = os.environ if source is None else source
        hidden = set(self.secret_names)
        return {
            str(key): str(value)
            for key, value in found.items()
            if key and not sensitive_name(str(key)) and str(key) not in hidden
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


def _read_named_secret(path: str, name: str) -> str:
    """Read one KEY=VALUE line. The value is not kept on the identity door."""
    if not path:
        raise RuntimeError(f"环境里没有这个密钥: {name}")
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"环境里没有这个密钥: {name}") from exc
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() != name:
            continue
        cleaned = value.strip().strip("'").strip('"')
        if cleaned:
            return cleaned
        break
    raise RuntimeError(f"环境里没有这个密钥: {name}")
