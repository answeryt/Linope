"""Working directory, environment variables, and standard streams."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kernel.environment.identity import sensitive_name


@dataclass(frozen=True)
class ProcessEnvironment:
    """Explicit OS execution inputs, separate from Agent Resource Context."""

    pid: int
    capability_id: str
    cwd: str
    argv: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    env_file: str = ""
    env_file_keys: tuple[str, ...] = ()
    inherit_parent_env: bool = True
    stdin: str = "ipc"
    stdout: str = "ipc"
    stderr: str = "inherit"

    def __post_init__(self) -> None:
        if self.pid <= 0:
            raise ValueError("pid must be a positive operating-system process id")
        if not self.capability_id.strip():
            raise ValueError("capability_id must not be empty")
        cwd = Path(self.cwd).expanduser().resolve()
        if not cwd.is_dir():
            raise ValueError(f"process cwd is not a directory: {cwd}")
        object.__setattr__(self, "cwd", str(cwd))
        for value in self.argv:
            if "\x00" in value:
                raise ValueError("argv cannot contain NUL characters")
        for key, value in self.env.items():
            if not key or "\x00" in key or "\x00" in value:
                raise ValueError("environment keys and values cannot contain NUL")
        if self.env_file_keys and not self.env_file:
            raise ValueError("No env file given; cannot select keys")
        for key in self.env_file_keys:
            if not key or "=" in key or "\x00" in key:
                raise ValueError(f"Invalid environment variable name: {key!r}")
        if self.env_file:
            path = Path(self.env_file).expanduser().resolve()
            if not path.is_file():
                raise ValueError(f"Env file does not exist: {path}")
            object.__setattr__(self, "env_file", str(path))
        for name, mode in (
            ("stdin", self.stdin),
            ("stdout", self.stdout),
            ("stderr", self.stderr),
        ):
            if mode not in {"ipc", "inherit", "null"}:
                raise ValueError(f"unsupported {name} mode: {mode!r}")

    @classmethod
    def current(
        cls,
        *,
        pid: int,
        capability_id: str,
        cwd: str | Path | None = None,
        env_file: str = "",
        env_file_keys: tuple[str, ...] = (),
    ) -> "ProcessEnvironment":
        """Record an explicit environment. Secret values stay out of the startup package."""
        return cls(
            pid=pid,
            capability_id=capability_id,
            cwd=str(cwd or Path.cwd()),
            env_file=env_file,
            env_file_keys=env_file_keys,
        )

    def apply(self) -> None:
        """Apply the working directory and explicit variables.

        The environment present at creation stays in place. It is replaced
        only when ``inherit_parent_env`` is false. Named env-file keys are
        checked so a missing key fails now, then removed from the process
        environment. Their values are read later from the file.
        """
        os.chdir(self.cwd)
        if not self.inherit_parent_env:
            os.environ.clear()
        os.environ.update(self.public_env())

    def public_env(self) -> dict[str, str]:
        """Variables safe to write into the startup package."""
        return {
            key: value
            for key, value in self.env.items()
            if not sensitive_name(key)
        }

    def payload(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "capability_id": self.capability_id,
            "cwd": self.cwd,
            "argv": list(self.argv),
            "env": self.public_env(),
            "env_file": self.env_file,
            "env_file_keys": list(self.env_file_keys),
            "inherit_parent_env": self.inherit_parent_env,
            "stdin": self.stdin,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ProcessEnvironment":
        return cls(
            pid=int(payload["pid"]),
            capability_id=str(payload["capability_id"]),
            cwd=str(payload["cwd"]),
            argv=tuple(str(value) for value in payload.get("argv", ())),
            env={str(key): str(value) for key, value in payload.get("env", {}).items()},
            env_file=str(payload.get("env_file", "")),
            env_file_keys=tuple(str(key) for key in payload.get("env_file_keys", ())),
            inherit_parent_env=bool(payload.get("inherit_parent_env", True)),
            stdin=str(payload.get("stdin", "ipc")),
            stdout=str(payload.get("stdout", "ipc")),
            stderr=str(payload.get("stderr", "inherit")),
        )


_API_KEY_ENV = re.compile(
    r"""["']api_key_env["']\s*:\s*["']([^"']+)["']"""
)
_SKIP_ENV_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        "deepseek-harness-master",
        "Agent-libOS-main",
    }
)


def api_key_names(module_paths: tuple[str, ...]) -> tuple[str, ...]:
    """Key names a capability card asks for. Values stay in the env file."""
    found: list[str] = []
    for raw in module_paths:
        path = Path(raw)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for match in _API_KEY_ENV.finditer(text):
            name = match.group(1).strip()
            if name and name not in found:
                found.append(name)
    return tuple(found)


def find_env_files(root: str | Path) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """List ``.env`` files under ``root``. Each item is a path and its key names.

    Values stay in the file. ``_read_env_file`` does the parsing.
    """
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        return ()
    found: list[tuple[str, tuple[str, ...]]] = []
    for directory, dirnames, filenames in os.walk(base):
        dirnames[:] = [name for name in dirnames if name not in _SKIP_ENV_DIRS]
        if ".env" not in filenames:
            continue
        path = Path(directory) / ".env"
        if not path.is_file():
            continue
        keys = tuple(_read_env_file(str(path), ()))
        found.append((str(path), keys))
    found.sort(key=lambda item: item[0])
    return tuple(found)


def _read_env_file(path: str, keys: tuple[str, ...]) -> dict[str, str]:
    """Read KEY=VALUE lines. Only the named keys are kept when names are given."""
    if not path:
        return {}
    found: dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            found[key] = value
    if not keys:
        return found
    missing = [key for key in keys if key not in found]
    if missing:
        raise ValueError(f"Env file has no such key: {missing[0]}")
    return {key: found[key] for key in keys}
