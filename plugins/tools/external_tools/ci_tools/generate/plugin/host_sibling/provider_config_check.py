# -*- coding: utf-8 -*-
"""Host-sibling check: model_provider templates stay format-equivalent data.

Each provider directory must ship YAML, JSON, and TOML with the same schema
keys. Files are data, not code — they must not perform SDK calls.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PLUGIN_NAME = "plugin_provider_config"
PLUGIN_VERSION = "1.0"

REQUIRED_TOP = ("provider", "interface", "model", "api_key_env", "parameters")
FORMATS = (".yaml", ".yml", ".json", ".toml")


def run(context: dict[str, Any]) -> dict[str, Any]:
    repo = Path(context["repo_root"])
    for family in context["families"]:
        root = repo / family["root"]
        if not root.is_dir():
            continue
        if not _looks_like_provider_root(root):
            continue
        for provider_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            if provider_dir.name in {"__pycache__", ".git"}:
                continue
            _check_provider_dir(context, repo, provider_dir)
    return context


def _looks_like_provider_root(root: Path) -> bool:
    for child in root.rglob("*.json"):
        if any(part in {"__pycache__", ".git"} for part in child.parts):
            continue
        try:
            payload = json.loads(child.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and all(key in payload for key in REQUIRED_TOP):
            return True
    return False


def _check_provider_dir(
    context: dict[str, Any],
    repo: Path,
    provider_dir: Path,
) -> None:
    rel_dir = provider_dir.relative_to(repo).as_posix()
    files = {
        path.suffix.lower(): path
        for path in provider_dir.iterdir()
        if path.is_file() and path.suffix.lower() in FORMATS
    }
    if ".yaml" not in files and ".yml" not in files:
        context["violations"].append(
            _violation("provider.formats", rel_dir, "missing YAML template")
        )
    if ".json" not in files:
        context["violations"].append(
            _violation("provider.formats", rel_dir, "missing JSON template")
        )
    if ".toml" not in files:
        context["violations"].append(
            _violation("provider.formats", rel_dir, "missing TOML template")
        )

    json_path = files.get(".json")
    payload: dict[str, Any] | None = None
    if json_path is not None:
        try:
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            context["violations"].append(
                _violation(
                    "provider.json",
                    json_path.relative_to(repo).as_posix(),
                    f"invalid JSON: {exc}",
                )
            )
        else:
            if not isinstance(loaded, dict):
                context["violations"].append(
                    _violation(
                        "provider.json",
                        json_path.relative_to(repo).as_posix(),
                        "JSON template must be an object",
                    )
                )
            else:
                payload = loaded
                _require_keys(
                    context,
                    json_path.relative_to(repo).as_posix(),
                    loaded,
                )
                interface = loaded.get("interface")
                if isinstance(interface, str) and interface:
                    interface_file = (
                        repo / "model" / "model_API" / "model_interface" / f"{interface}.py"
                    )
                    if not interface_file.is_file():
                        context["violations"].append(
                            _violation(
                                "provider.interface",
                                json_path.relative_to(repo).as_posix(),
                                f"interface `{interface}` has no "
                                f"model_interface/{interface}.py",
                            )
                        )

    yaml_path = files.get(".yaml") or files.get(".yml")
    if yaml_path is not None:
        _require_text_keys(
            context,
            yaml_path.relative_to(repo).as_posix(),
            yaml_path.read_text(encoding="utf-8"),
            payload,
        )
    toml_path = files.get(".toml")
    if toml_path is not None:
        _require_text_keys(
            context,
            toml_path.relative_to(repo).as_posix(),
            toml_path.read_text(encoding="utf-8"),
            payload,
        )


def _require_keys(
    context: dict[str, Any],
    rel: str,
    payload: dict[str, Any],
) -> None:
    for key in REQUIRED_TOP:
        if key not in payload:
            context["violations"].append(
                _violation(
                    "provider.schema",
                    rel,
                    f"missing required top-level key `{key}`",
                )
            )


def _require_text_keys(
    context: dict[str, Any],
    rel: str,
    text: str,
    payload: dict[str, Any] | None,
) -> None:
    for key in REQUIRED_TOP:
        if not _has_key(text, key):
            context["violations"].append(
                _violation(
                    "provider.schema",
                    rel,
                    f"missing required top-level key `{key}`",
                )
            )
    if not payload:
        return
    for key in ("provider", "interface"):
        expected = payload.get(key)
        if isinstance(expected, str) and expected and expected not in text:
            context["violations"].append(
                _violation(
                    "provider.equivalent",
                    rel,
                    f"`{key}` must match JSON value `{expected}`",
                )
            )


def _has_key(text: str, key: str) -> bool:
    return bool(
        re.search(rf'(?m)^[ \t]*{re.escape(key)}\s*[:=]', text)
        or re.search(rf'(?m)^[ \t]*\[{re.escape(key)}\]', text)
        or re.search(rf'"{re.escape(key)}"\s*:', text)
    )


def _violation(rule: str, path: str, detail: str) -> dict[str, str]:
    return {"rule": rule, "path": path, "detail": detail, "severity": "error"}
