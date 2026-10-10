"""Storage locator parsing and project-level default selection."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

DEFAULT_FILE_LOCATOR = "file:.linope/resources.json"
def normalize_locator(value: str | Path | None) -> str:
    if value is None or str(value).strip() == "":
        return default_store_locator()
    raw = str(value)
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw) is not None and not (
        len(raw) >= 2 and raw[1] == ":"
    ):
        return raw
    return f"file:{raw}"


def default_store_locator() -> str:
    raw = os.environ.get("LINOPE_RESOURCE_STORE")
    if raw:
        return normalize_locator(raw)
    stored = _load_config().get("resource_store")
    if not stored:
        return DEFAULT_FILE_LOCATOR
    return normalize_locator(stored)


def set_default_store_locator(locator: str | Path) -> str:
    value = normalize_locator(locator)
    if value.startswith(("postgres://", "postgresql://", "mysql://")):
        if urlsplit(value).password is not None:
            raise ValueError(
                "默认存储配置不能保存数据库密码，请使用环境变量或系统凭据"
            )
    payload = _load_config()
    payload["resource_store"] = value
    _save_config(payload)
    return value


def default_env_file() -> str:
    """Path recorded by ``linope env``, or empty when none was chosen."""
    raw = _load_config().get("env_file") or ""
    return str(raw).strip()


def set_default_env_file(path: str | Path) -> str:
    """Remember one secret file. The value is a path, never a secret."""
    value = str(Path(path).expanduser().resolve())
    payload = _load_config()
    payload["env_file"] = value
    _save_config(payload)
    return value


def _load_config() -> dict[str, Any]:
    config = project_config_path()
    try:
        payload = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _save_config(payload: dict[str, Any]) -> None:
    config = project_config_path()
    config.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{config.name}.",
        dir=config.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, config)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def project_config_path() -> Path:
    return Path(".linope") / "config.json"


def local_path(locator: str | Path) -> Path:
    raw = str(locator)
    if raw.startswith(("file:", "local:")):
        raw = raw.split(":", 1)[1]
    if raw.startswith("//"):
        raw = raw[2:]
    return Path(raw).expanduser()


def locator_description(locator: str | Path) -> dict[str, Any]:
    normalized = normalize_locator(locator)
    try:
        from kernel.resource.store.registry import backend_for

        backend = backend_for(normalized)
    except KeyError:
        backend = "unknown"
    return {"locator": normalized, "backend": backend}
