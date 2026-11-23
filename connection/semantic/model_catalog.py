"""Discover model provider cards without using the ordinary capability table."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from capability.model.model_provider.card_profile import declaration_from_card


def discover_model_cards(repo_root: str | Path | None = None) -> list[dict[str, Any]]:
    """Return metadata for every loadable model provider card."""

    root = Path(repo_root or Path(__file__).resolve().parents[2]).resolve()
    provider_root = root / "capability" / "model" / "model_provider"
    cards: list[dict[str, Any]] = []
    if not provider_root.is_dir():
        return cards

    for plugin_path in sorted(provider_root.glob("*/*_plugin.py")):
        cards.append(_describe_plugin(plugin_path, root))
    return cards


def _describe_plugin(plugin_path: Path, repo_root: Path) -> dict[str, Any]:
    plugin_name = plugin_path.parent.name
    capability = f"model.{plugin_name}"
    base: dict[str, Any] = {
        "capability": capability,
        "plugin": plugin_name,
        "ready": False,
        "error": None,
    }
    try:
        module = _load_module(plugin_path)
        config = getattr(module, "CARD_CONFIG", None)
        if not isinstance(config, dict):
            raise ValueError("CARD_CONFIG must be a mapping")
        card_id = str(config.get("card_id") or plugin_name)
        card_path = plugin_path.parent / f"{card_id}.json"
        sidecar = _load_json(card_path)
        changes = _changes(config)
        declaration = declaration_from_card(capability, config, ())
        interface = str(sidecar.get("interface") or config.get("interface") or "")
        interface_path = (
            repo_root
            / "capability"
            / "model"
            / "model_API"
            / "model_interface"
            / f"{interface}.py"
        )
        base.update(
            {
                "card_id": card_id,
                "provider": str(config.get("provider") or sidecar.get("provider") or ""),
                "interface": interface,
                "model": declaration.model,
                "base_url": str(
                    config.get("base_url")
                    or sidecar.get("base_url")
                    or ""
                ),
                "api_key_env": str(config.get("api_key_env") or sidecar.get("api_key_env") or ""),
                "organization_env": str(
                    config.get("organization_env")
                    or sidecar.get("organization_env")
                    or ""
                ),
                "parameters": _json_value(config.get("parameters") or {}),
                "changes": changes,
                "context_limit": declaration.context_limit,
                "card_json": card_path.relative_to(repo_root).as_posix()
                if card_path.is_relative_to(repo_root)
                else str(card_path),
                "card_json_exists": card_path.is_file(),
                "interface_exists": interface_path.is_file(),
                "ready": card_path.is_file() and interface_path.is_file(),
            }
        )
        if not base["ready"]:
            base["error"] = "model card JSON or interface is missing"
    except Exception as exc:
        base["error"] = str(exc)
    return base


def _load_module(path: Path) -> Any:
    name = f"linope_model_catalog_{path.parent.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"model card must be an object: {path}")
    return value


def _changes(config: dict[str, Any]) -> list[str]:
    parameters = config.get("parameters")
    names = set(parameters) if isinstance(parameters, dict) else set()
    names.update({"model", "provider", "base_url", "stream", "permission", "capabilities"})
    return sorted(str(name) for name in names)


def _json_value(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)
    return value
