"""Keep environment references and temporary secrets outside command payloads."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from connection.protocol.request import ProtocolError


@dataclass
class TemporaryEnvironmentFile:
    """A host-owned environment file that can be removed after use."""

    path: Path

    def cleanup(self) -> None:
        """Remove the temporary file if it still exists."""

        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def validate_environment_reference(path: str, keys: tuple[str, ...] = ()) -> tuple[str, tuple[str, ...]]:
    """Validate an environment file reference without reading secret values."""

    clean_path = path.strip()
    if not clean_path:
        raise ProtocolError("invalid_environment", "Environment path must not be empty")
    clean_keys = tuple(_validate_key(key) for key in keys)
    return clean_path, clean_keys


def write_secret_file(values: Mapping[str, str]) -> TemporaryEnvironmentFile:
    """Write host-provided secrets to a private temporary env file."""

    if not values:
        raise ProtocolError("invalid_environment", "At least one environment value is required")
    lines: list[str] = []
    for raw_key, value in values.items():
        key = _validate_key(raw_key)
        if not isinstance(value, str):
            raise ProtocolError("invalid_environment", f"Environment value for {key} must be a string")
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ProtocolError("invalid_environment", f"Environment value for {key} contains a newline")
        lines.append(f"{key}={value}")

    descriptor, raw_path = tempfile.mkstemp(prefix="linope-env-", suffix=".env")
    os.close(descriptor)
    path = Path(raw_path)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return TemporaryEnvironmentFile(path)


def _validate_key(value: str) -> str:
    if not isinstance(value, str):
        raise ProtocolError("invalid_environment", "Environment keys must be strings")
    key = value.strip()
    if not key or "=" in key or "\x00" in key or any(char.isspace() for char in key):
        raise ProtocolError("invalid_environment", "Environment keys must be non-empty names")
    return key
