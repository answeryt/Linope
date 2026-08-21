# -*- coding: utf-8 -*-
"""Write the generated deny list in the Host-selected card format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PLUGIN_NAME = "plugin_deny_generate"
PLUGIN_VERSION = "1.0"

CARD_DIR = Path(__file__).resolve().parent / "deny_list_crad"
LIST_STEM = "list"
FORMAT_ORDER = ("json", "yaml", "toml", "md")
FORMAT_ALIASES = {"yml": "yaml", "markdown": "md"}


def run(context: dict[str, Any]) -> dict[str, Any]:
    fmt = _normalize_format(context.get("format"))
    payload = _payload(context)
    text = _render(payload, fmt)
    _emit(context, CARD_DIR / f"{LIST_STEM}.{fmt}", text)
    return context


def _payload(context: dict[str, Any]) -> dict[str, Any]:
    families = [
        str(family["root"]).replace("\\", "/")
        for family in (context.get("families") or [])
    ]
    return {"families": families}


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
    for key, value in payload.items():
        items = value if isinstance(value, list) else [value]
        lines.append(f"{key} = [")
        for item in items:
            lines.append(f"  {json.dumps(str(item), ensure_ascii=False)},")
        lines.append("]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_md(payload: dict[str, Any]) -> str:
    lines = ["# Deny list", ""]
    for key, value in payload.items():
        lines.append(f"## {key}")
        lines.append("")
        items = value if isinstance(value, list) else [value]
        if not items:
            lines.append("None.")
        else:
            for item in items:
                lines.append(f"- `{item}`")
        lines.append("")
    return "\n".join(lines)
