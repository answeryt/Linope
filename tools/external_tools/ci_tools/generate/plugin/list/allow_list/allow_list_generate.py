# -*- coding: utf-8 -*-
"""Write the handwritten allow list in the Host-selected card format."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any


PLUGIN_NAME = "plugin_allow_generate"
PLUGIN_VERSION = "1.0"

CARD_DIR = Path(__file__).resolve().parent / "allow_list_card"
LIST_STEM = "list"
FORMAT_ORDER = ("json", "yaml", "toml", "md")
FORMAT_ALIASES = {"yml": "yaml", "markdown": "md"}


def load(fmt: str | None = None) -> dict[str, Any]:
    """Read the handwritten allow-list card. Prefer ``fmt``, then other cards."""
    for name in _format_candidates(fmt):
        path = CARD_DIR / f"{LIST_STEM}.{name}"
        if not path.is_file():
            continue
        payload = _parse(path, name)
        if payload:
            return payload
    return {}


def run(context: dict[str, Any]) -> dict[str, Any]:
    fmt = _normalize_format(context.get("format"))
    payload = _payload(context.get("allow_list") or {})
    text = _render(payload, fmt)
    _emit(context, CARD_DIR / f"{LIST_STEM}.{fmt}", text)
    return context


def _payload(allow_list: dict[str, Any]) -> dict[str, Any]:
    paths = [
        str(item).replace("\\", "/")
        for item in (allow_list.get("paths") or allow_list.get("except") or [])
    ]
    inject = allow_list.get("inject")
    result: dict[str, Any] = {"paths": paths}
    if isinstance(inject, dict):
        result["inject"] = {
            str(stem): [str(name) for name in names]
            for stem, names in inject.items()
            if isinstance(names, (list, tuple))
        }
    for key in ("kernel_layers",):
        inventory = allow_list.get(key)
        if isinstance(inventory, dict):
            result[key] = {
                str(name): [str(item) for item in items]
                for name, items in inventory.items()
                if isinstance(items, (list, tuple))
            }
    return result


def _emit(context: dict[str, Any], path: Path, text: str) -> None:
    rel = _rel(context, path)
    context.setdefault("generated", []).append(rel)
    if context.get("check"):
        committed = path.read_text(encoding="utf-8") if path.is_file() else None
        if committed != text:
            context.setdefault("stale", []).append(rel)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _rel(context: dict[str, Any], path: Path) -> str:
    repo = Path(context.get("repo_root") or ".")
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _normalize_format(raw: Any) -> str:
    name = str(raw or "json").lower().lstrip(".")
    name = FORMAT_ALIASES.get(name, name)
    return name if name in FORMAT_ORDER else "json"


def _format_candidates(fmt: str | None) -> list[str]:
    ordered: list[str] = []
    chosen = _normalize_format(fmt) if fmt else None
    if chosen:
        ordered.append(chosen)
    for name in FORMAT_ORDER:
        if name not in ordered:
            ordered.append(name)
    return ordered


def _parse(path: Path, fmt: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if fmt == "json":
        payload = json.loads(text)
    elif fmt == "toml":
        import tomllib

        payload = tomllib.loads(text)
    elif fmt == "yaml":
        payload = _parse_yaml(text)
    else:
        payload = _parse_md(text)
    return payload if isinstance(payload, dict) else {}


def _parse_yaml(text: str) -> dict[str, Any]:
    try:
        yaml = importlib.import_module("yaml")
    except ImportError:
        return _parse_simple_yaml(text)
    payload = yaml.safe_load(text)
    return payload if isinstance(payload, dict) else {}


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key: str | None = None
    nested: dict[str, Any] | None = None
    nested_key: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.endswith(":") and not line.startswith(" "):
            current_key = line[:-1].strip()
            nested = None
            nested_key = None
            result[current_key] = []
            continue
        if current_key is None:
            continue
        if line.startswith("    - ") and nested is not None and nested_key:
            nested[nested_key].append(_unquote(line[6:].strip()))
            continue
        if line.startswith("  - ") and nested is None:
            if not isinstance(result[current_key], list):
                result[current_key] = []
            result[current_key].append(_unquote(line[4:].strip()))
            continue
        if line.startswith("  ") and line.endswith(":"):
            nested_key = line.strip()[:-1]
            if nested is None:
                nested = {}
                result[current_key] = nested
            nested[nested_key] = []
    return result


def _parse_md(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    section: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            section = line[3:].strip()
            result[section] = (
                {}
                if section in {"inject", "kernel_layers"}
                else []
            )
            continue
        if section is None or not line.startswith("- "):
            continue
        item = line[2:].strip()
        if isinstance(result[section], dict):
            key, _, rest = item.partition(":")
            names = [
                part.strip().strip("`")
                for part in rest.split(",")
                if part.strip()
            ]
            result[section][key.strip().strip("`")] = names
            continue
        if isinstance(result[section], list):
            result[section].append(item.strip("`"))
    return result


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _render(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if fmt == "toml":
        return _render_toml(payload)
    if fmt == "md":
        return _render_md(payload)
    return _render_yaml(payload)


def _render_yaml(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            if not value:
                lines.append("  {}")
                continue
            for inner_key, inner_value in value.items():
                lines.append(f"  {inner_key}:")
                items = inner_value if isinstance(inner_value, list) else [inner_value]
                if not items:
                    lines.append("    []")
                    continue
                for item in items:
                    lines.append(f"    - {item}")
            continue
        lines.append(f"{key}:")
        items = value if isinstance(value, list) else [value]
        if not items:
            lines.append("  []")
            continue
        for item in items:
            lines.append(f"  - {item}")
    return "\n".join(lines) + "\n"


def _render_toml(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    tables: list[tuple[str, dict[str, Any]]] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            tables.append((key, value))
            continue
        lines.extend(_toml_array(key, value if isinstance(value, list) else [value]))
        lines.append("")
    for key, table in tables:
        lines.append(f"[{key}]")
        for inner_key, inner_value in table.items():
            items = inner_value if isinstance(inner_value, list) else [inner_value]
            joined = ", ".join(_toml_str(item) for item in items)
            lines.append(f"{inner_key} = [{joined}]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _toml_array(key: str, items: list[Any]) -> list[str]:
    lines = [f"{key} = ["]
    for item in items:
        lines.append(f"  {_toml_str(item)},")
    lines.append("]")
    return lines


def _toml_str(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _render_md(payload: dict[str, Any]) -> str:
    lines = ["# Allow list", ""]
    for key, value in payload.items():
        lines.append(f"## {key}")
        lines.append("")
        if isinstance(value, dict):
            if not value:
                lines.append("None.")
            else:
                for inner_key, inner_value in value.items():
                    items = inner_value if isinstance(inner_value, list) else [inner_value]
                    names = ", ".join(f"`{item}`" for item in items)
                    lines.append(f"- `{inner_key}`: {names}")
        else:
            items = value if isinstance(value, list) else [value]
            if not items:
                lines.append("None.")
            else:
                for item in items:
                    lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines)
