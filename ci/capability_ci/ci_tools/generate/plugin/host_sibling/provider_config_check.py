# -*- coding: utf-8 -*-
"""Host-sibling check: a model provider card is one JSON file.

Each provider directory ships `<name>.json`. The file is data, not code —
it must not perform SDK calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PLUGIN_NAME = "plugin_provider_config"
PLUGIN_VERSION = "1.0"

REQUIRED_TOP = ("provider", "interface", "model", "api_key_env", "parameters")


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
    json_path = provider_dir / f"{provider_dir.name}.json"
    if not json_path.is_file():
        context["violations"].append(
            _violation("provider.formats", rel_dir, "missing JSON card")
        )
        return
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
        return
    if not isinstance(loaded, dict):
        context["violations"].append(
            _violation(
                "provider.json",
                json_path.relative_to(repo).as_posix(),
                "JSON card must be an object",
            )
        )
        return
    rel = json_path.relative_to(repo).as_posix()
    _require_keys(context, rel, loaded)
    interface = loaded.get("interface")
    if isinstance(interface, str) and interface:
        interface_file = _interface_file(repo, interface)
        if interface_file is None:
            context["violations"].append(
                _violation(
                    "provider.interface",
                    rel,
                    f"interface `{interface}` has no model_interface/{interface}.py",
                )
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


def _interface_file(repo: Path, interface: str) -> Path | None:
    for relative in (
        Path("model") / "model_API" / "model_interface" / f"{interface}.py",
        Path("capability") / "model" / "model_API" / "model_interface" / f"{interface}.py",
    ):
        candidate = repo / relative
        if candidate.is_file():
            return candidate
    return None


def _violation(rule: str, path: str, detail: str) -> dict[str, str]:
    return {"rule": rule, "path": path, "detail": detail, "severity": "error"}
