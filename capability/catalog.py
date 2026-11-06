"""Write the capability table. The kernel only reads the finished file."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


TABLE_NAME = "programs.json"
_SKIP = {"__pycache__", ".git", "tests"}
_LOAD_SEQ = 0


def main(argv: list[str] | None = None) -> None:
    """Write ``programs.json`` beside this package."""
    root = Path(__file__).resolve().parent
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments:
        root = Path(arguments[0]).resolve()
    destination = root / TABLE_NAME
    write_table(root, destination)


def write_table(root: Path, destination: Path) -> dict[str, Any]:
    """Build the table from plugins and package manifests, then store it."""
    table = build_table(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(table, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return table


def build_table(root: Path) -> dict[str, Any]:
    """One row per capability. A failing profile is left out."""
    root = root.resolve()
    repo = root.parent
    chosen: dict[str, Path] = {}
    for path in [*_files(root, "*_plugin.py"), *_files(root, "prompt_main.py")]:
        name = _plugin_name(root, path)
        if name is None:
            continue
        chosen[name] = path
    table: dict[str, Any] = {}
    for name in sorted(chosen):
        row = _plugin_row(repo, name, chosen[name])
        if row is not None:
            table[name] = row
    for path in _files(root, "linope.json"):
        row = _manifest_row(path)
        if row is not None:
            table[str(row.pop("name"))] = row
    return table


def _files(root: Path, pattern: str) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        if any(part in _SKIP for part in path.parts):
            continue
        found.append(path)
    return sorted(found)


def _plugin_name(root: Path, path: Path) -> str | None:
    """The name printed at startup. The rules live with the capability tree."""
    text = _text(path)
    if "def load(" not in text and "async def load(" not in text:
        return None
    relative = path.relative_to(root)
    parts = relative.parts
    family = parts[0] if len(parts) > 1 else ""
    stem = path.name[: -len("_plugin.py")] if path.name.endswith("_plugin.py") else path.stem
    if path.name == "prompt_main.py" and family == "prompt":
        return f"prompt.{path.parent.name}"
    if not path.name.endswith("_plugin.py") or not family:
        return None
    if family == "model":
        return f"model.{path.parent.name}"
    if family == "tools":
        return f"tools.{stem}"
    if family == "sandbox":
        if len(parts) == 2:
            return f"sandbox.{stem}"
        return "sandbox.sandbox"
    return f"{family}.{stem}"


def _plugin_row(repo: Path, name: str, path: Path) -> dict[str, Any] | None:
    try:
        module = _load(path)
        profile = getattr(module, "capability_profile", None)
        if not callable(profile):
            return None
        declaration = profile(name, ())
    except (Exception, SystemExit):
        return None
    resources = getattr(declaration, "resources", None)
    if resources is None:
        return None
    relative = path.resolve().relative_to(repo.resolve()).as_posix()
    try:
        payload = {
            "argv": ["python", "-m", "capability.program", relative],
            "module_paths": [relative],
            "entrypoint": "load",
            "resources": [_claim(item) for item in resources],
            "settings": dict(getattr(declaration, "settings", None) or {}),
            "changes": _change_names(module),
            "secret_names": _secret_names(module),
        }
        schemas = _schemas(module)
        if schemas:
            payload["schemas"] = schemas
        json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        return None
    return payload


def _manifest_row(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    name = str(payload.get("name") or "").strip()
    command = payload.get("command")
    if not name or not isinstance(command, list) or not command:
        return None
    resources = payload.get("resources") or []
    if not isinstance(resources, list):
        return None
    return {
        "name": name,
        "argv": [str(item) for item in command],
        "module_paths": [],
        "entrypoint": "load",
        "resources": [dict(item) for item in resources if isinstance(item, dict)],
        "settings": dict(payload.get("settings") or {}),
        "changes": [str(item) for item in payload.get("changes") or ()],
        "secret_names": [str(item) for item in payload.get("secrets") or ()],
    }


def _change_names(module: Any) -> list[str]:
    named = getattr(module, "CAPABILITY_CHANGES", None)
    if isinstance(named, (list, tuple)) and named:
        return sorted({str(item) for item in named if str(item).strip()})
    card = getattr(module, "CARD_CONFIG", None)
    if not isinstance(card, dict):
        return []
    parameters = card.get("parameters") or {}
    if not isinstance(parameters, dict):
        parameters = {}
    return sorted(set(parameters) | {"model", "provider", "base_url"})


def _schemas(module: Any) -> list[Any] | None:
    """The plugin's own tool declarations, when they can be stored as JSON."""
    reader = getattr(module, "tool_schemas", None)
    if not callable(reader):
        return None
    try:
        value = reader()
    except (Exception, SystemExit):
        return None
    if not isinstance(value, list) or not value:
        return None
    return value


def _secret_names(module: Any) -> list[str]:
    card = getattr(module, "CARD_CONFIG", None)
    if not isinstance(card, dict):
        return []
    name = str(card.get("api_key_env") or "").strip()
    if not name:
        return []
    return [name]


def _claim(item: Any) -> dict[str, Any]:
    kind = getattr(item, "kind", "")
    return {
        "kind": str(getattr(kind, "value", kind)),
        "identity": dict(getattr(item, "identity", None) or {}),
        "call_params": dict(getattr(item, "call_params", None) or {}),
    }


def _load(path: Path) -> Any:
    global _LOAD_SEQ
    _LOAD_SEQ += 1
    name = f"linope_catalog_{_LOAD_SEQ}_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


if __name__ == "__main__":
    main()
