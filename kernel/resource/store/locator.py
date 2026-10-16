"""Storage locator parsing and project-level default selection."""

from __future__ import annotations

import json
import os
import sys
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
    if re.match(r"^[A-Za-z][A-Za-z0-9+._-]*:", raw) is not None and not (
        len(raw) >= 2 and raw[1] == ":"
    ):
        return raw
    return f"file:{raw}"


def default_store_locator() -> str:
    raw = os.environ.get("LINOPE_RESOURCE_STORE")
    if raw:
        return normalize_locator(raw)
    stored = _load_project().get("resource_store")
    if not stored:
        stored = _read_json(user_config_path()).get("resource_store")
    if not stored:
        return DEFAULT_FILE_LOCATOR
    return normalize_locator(str(stored))


def set_default_store_locator(locator: str | Path) -> str:
    value = normalize_locator(locator)
    _reject_saved_password(value)
    portable = _portable_store(value)
    user = _read_json(user_config_path())
    if portable is None:
        user["resource_store"] = value
        _write_json(user_config_path(), user)
        return value
    if "resource_store" in user:
        user.pop("resource_store", None)
        _write_json(user_config_path(), user)
    payload = _load_project()
    payload["resource_store"] = portable
    _save_project(payload)
    return portable


def _reject_saved_password(value: str) -> None:
    if "://" not in value or urlsplit(value).password is None:
        return
    raise ValueError("默认存储配置不能保存数据库密码，请使用环境变量或系统凭据")


def default_env_file() -> str:
    """Path recorded for this user, or empty when none was chosen."""
    override = os.environ.get("LINOPE_ENV_FILE", "").strip()
    if override:
        chosen = _existing_file(override)
        if chosen:
            return chosen
    _load_project()
    return _existing_file(str(_read_json(user_config_path()).get("env_file") or ""))


def env_file_problem() -> str:
    """A message when the remembered secret file can no longer be opened."""
    stored = str(_read_json(user_config_path()).get("env_file") or "").strip()
    if stored and not Path(stored).expanduser().is_file():
        return "之前记下的环境文件已经不存在，请重新选择。"
    notice = str(_read_json(user_config_path()).get("env_notice") or "").strip()
    return notice


def set_default_env_file(path: str | Path) -> str:
    """Remember one secret file for this user. The value is a path, never a secret."""
    value = str(Path(path).expanduser().resolve())
    payload = _read_json(user_config_path())
    payload["env_file"] = value
    payload.pop("env_notice", None)
    _write_json(user_config_path(), payload)
    return value


def read_project_config() -> dict[str, Any]:
    """The project config. Callers add their own keys and write it back."""
    return _load_project()


def write_project_config(payload: dict[str, Any]) -> None:
    """Replace the project config. A database password or secret path cannot be saved."""
    stored = payload.get("resource_store")
    if stored:
        _reject_saved_password(str(stored))
    data = dict(payload)
    data.pop("env_file", None)
    _save_project(data)


def project_root() -> Path:
    """The kernel checkout, independent of the directory from which a command was started."""
    from kernel.process.process_creat.instances import repo_root

    root = repo_root()
    if (root / "pyproject.toml").is_file() and (root / "kernel").is_dir():
        return root
    return Path.cwd()


def project_config_path() -> Path:
    return project_root() / ".linope" / "config.json"


def user_config_dir() -> Path:
    """The per-user configuration directory. It is never inside a shared project tree."""
    override = os.environ.get("LINOPE_USER_CONFIG_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "Linope"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Linope"
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "linope"


def user_config_path() -> Path:
    return user_config_dir() / "config.json"


def _load_config() -> dict[str, Any]:
    return _load_project()


def _load_project() -> dict[str, Any]:
    path = project_config_path()
    payload = _read_json(path)
    migrated, changed = _migrate_project(payload)
    if changed:
        _save_project(migrated)
    return migrated


def _migrate_project(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Move machine-specific values out of the copyable project file."""
    data = dict(payload)
    changed = False
    env_file = data.get("env_file")
    if isinstance(env_file, str) and env_file.strip():
        data.pop("env_file", None)
        changed = True
        _migrate_env_file(env_file.strip())
    store = data.get("resource_store")
    if isinstance(store, str) and store.strip():
        portable = _portable_store(store)
        if portable != store:
            changed = True
            if portable is None:
                data.pop("resource_store", None)
                _migrate_external_store(store)
            else:
                data["resource_store"] = portable
    return data, changed


def _migrate_env_file(raw: str) -> None:
    user = _read_json(user_config_path())
    if str(user.get("env_file") or "").strip():
        return
    path = Path(raw).expanduser()
    if path.is_file():
        user["env_file"] = str(path.resolve())
        user.pop("env_notice", None)
    else:
        user["env_notice"] = "之前记下的环境文件已经不存在，请重新选择。"
    _write_json(user_config_path(), user)


def _migrate_external_store(raw: str) -> None:
    path = _locator_path(raw)
    if path is None or not path.is_file():
        return
    user = _read_json(user_config_path())
    if user.get("resource_store"):
        return
    user["resource_store"] = normalize_locator(str(path))
    _write_json(user_config_path(), user)


def _portable_store(value: str) -> str | None:
    """Return a project-relative locator, or none when it cannot travel with the project."""
    normalized = normalize_locator(value)
    if not normalized.startswith(("file:", "local:")):
        return normalized
    path = _locator_path(normalized)
    if path is None:
        return None
    if not path.is_absolute():
        return "file:" + Path(str(path)).as_posix()
    try:
        relative = path.resolve().relative_to(project_root().resolve())
    except ValueError:
        return None
    return "file:" + relative.as_posix()


def _locator_path(value: str) -> Path | None:
    raw = str(value)
    if raw.startswith(("file:", "local:")):
        raw = raw.split(":", 1)[1]
    if not raw or raw.startswith("//"):
        return None
    return Path(raw).expanduser()


def _existing_file(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    path = Path(text).expanduser()
    if not path.is_file():
        return ""
    return str(path.resolve())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _save_project(payload: dict[str, Any]) -> None:
    _write_json(project_config_path(), payload)


def _save_config(payload: dict[str, Any]) -> None:
    _save_project(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def local_path(locator: str | Path) -> Path:
    raw = str(locator)
    if raw.startswith(("file:", "local:")):
        raw = raw.split(":", 1)[1]
    if raw.startswith("//"):
        raw = raw[2:]
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = project_root() / path
    return path


def locator_description(locator: str | Path) -> dict[str, Any]:
    normalized = normalize_locator(locator)
    try:
        from kernel.resource.store.registry import backend_for

        backend = backend_for(normalized)
    except KeyError:
        backend = "unknown"
    return {"locator": normalized, "backend": backend}
