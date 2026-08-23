# -*- coding: utf-8 -*-
"""Write the services-layer Process-driven architecture.

Code-shape rules stay in ``generate/plugin``. This file only records the
architecture: Agent = Service + Resources and Service owns deployment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PLUGIN_NAME = "services_architecture"
PLUGIN_VERSION = "1.0"

CARD_DIR = Path(__file__).resolve().parent / "architecture_card"
LIST_STEM = "list"
FORMAT_ORDER = ("json", "yaml", "toml", "md")
FORMAT_ALIASES = {"yml": "yaml", "markdown": "md"}

VOCABULARY = {
    "Agent": "Service 与 Resources 的最终装配结果。",
    "Service": "唯一部署边界；接收 ProcessActivation 并运行 Process。",
    "Ingress": "把外部输入规范化为可序列化 Activation。",
    "RunQueue": "使用 lease 与 fencing token 调度 Process/Task 工作。",
    "ProcessStore": "Host 注入的 Process Run 持久化接口。",
    "Resources": "容器资源与模型资源组成的统一容量池。",
}

TREE = """\
Agent
├── Service
│   ├── Ingress
│   ├── Worker
│   ├── Run Queue
│   ├── Process Store
│   └── Agent Assembly
└── Resources
    ├── Container Resources
    └── Model Resources\
"""

ARCHITECTURE: dict[str, Any] = {
    "layer": "services",
    "role": "service",
    "title": "services：Agent = Service + Resources",
    "vocabulary": VOCABULARY,
    "tree": TREE,
    "owns": ["App", "Ingress", "Worker", "RunQueue", "ProcessStore"],
    "requirements": [
        "Agent 严格等于 Service + Resources，不是人格或进程层级。",
        "Service 是唯一部署边界，一个 Service 可以运行多个 Process。",
        "Ingress 只传可序列化 ProcessActivation，不传 live Process。",
        "Worker 使用 queue lease 和 fencing token 驱动 Process Runtime。",
        "Store、Queue 和 Ingress 是 Host adapter，不进入 Process 定义。",
        "OS process、worker、队列和部署框架只能出现在 services。",
    ],
}


def run(context: dict[str, Any]) -> dict[str, Any]:
    formats = _formats(context.get("format"))
    for fmt in formats:
        _emit(context, CARD_DIR / f"{LIST_STEM}.{fmt}", _render(ARCHITECTURE, fmt))
    return context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write services architecture cards")
    parser.add_argument("--format", default="all", help="json | yaml | toml | md | all")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    context: dict[str, Any] = {
        "repo_root": _repo_root(),
        "format": args.format,
        "check": args.check,
        "generated": [],
        "stale": [],
    }
    run(context)
    if context.get("stale"):
        print("stale architecture cards:", *context["stale"], sep="\n  ", file=sys.stderr)
        return 1
    return 0


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "kernel").is_dir() and (candidate / "tools").is_dir():
            return candidate
    return current.parents[4]


def _formats(raw: Any) -> tuple[str, ...]:
    name = str(raw or "all").lower().lstrip(".")
    name = FORMAT_ALIASES.get(name, name)
    if name in {"all", "*"}:
        return FORMAT_ORDER
    return (name,) if name in FORMAT_ORDER else ("md",)


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


def _render(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if fmt == "toml":
        return _render_toml(payload)
    if fmt == "md":
        return _render_md(payload)
    return _render_yaml(payload)


def _render_md(payload: dict[str, Any]) -> str:
    lines = [f"# {payload['title']}", "", "## 词汇", ""]
    for key, value in payload["vocabulary"].items():
        lines.append(f"- **{key}**：{value}")
    lines.extend(["", "## 结构", "", "```", payload["tree"], "```", "", "## 本层拥有", ""])
    for item in payload["owns"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## 架构要求", ""])
    for index, item in enumerate(payload["requirements"], start=1):
        lines.append(f"{index}. {item}")
    lines.append("")
    return "\n".join(lines)


def _render_yaml(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for inner_key, inner_value in value.items():
                lines.append(f"  {inner_key}: {_scalar(inner_value)}")
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_scalar(item)}")
            continue
        if isinstance(value, str) and "\n" in value:
            lines.append(f"{key}: |")
            lines.extend(f"  {row}" for row in value.splitlines())
            continue
        lines.append(f"{key}: {_scalar(value)}")
    return "\n".join(lines) + "\n"


def _render_toml(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    tables: list[tuple[str, dict[str, Any]]] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            tables.append((key, value))
            continue
        if isinstance(value, list):
            lines.append(f"{key} = [")
            for item in value:
                lines.append(f"  {_scalar(item)},")
            lines.append("]")
            lines.append("")
            continue
        if isinstance(value, str) and "\n" in value:
            lines.append(f'{key} = """')
            lines.append(value)
            lines.append('"""')
            lines.append("")
            continue
        lines.append(f"{key} = {_scalar(value)}")
        lines.append("")
    for key, table in tables:
        lines.append(f"[{key}]")
        for inner_key, inner_value in table.items():
            lines.append(f"{inner_key} = {_scalar(inner_value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _scalar(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
