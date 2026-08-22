# -*- coding: utf-8 -*-
"""Write the services-layer kernel architecture (Microservice / Task).

Code-shape rules stay in ``generate/plugin``. This file only records the
architecture: vocabulary, the Process tree, and what the Agent body owns.
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
    "Microservice": "部署边界。微服务指 Agent 本体。",
    "Process": "一个具有独立目标、状态、资源和生命周期的 Agent Work Unit。",
    "Execution": "Process 内部可被 Scheduler 独立调度的最小执行单元。",
    "Task": "用户/Agent 想要完成的目标。",
    "Loop": "Execution 使用的控制机制。",
    "Event": "Runtime 中发生的状态变化。",
}

TREE = """\
Microservice
                      │
                   Process
                      │
          ┌───────────┼───────────┐
          │           │           │
        State      Resources    Memory
                      │
                  Scheduler
                      │
            ┌─────────┼─────────┐
            ↓         ↓         ↓
        Execution  Execution  Execution
            │         │         │
          Agent      Tool      Event
           Loop       Loop      Loop\
"""

ARCHITECTURE: dict[str, Any] = {
    "layer": "services",
    "role": "microservice",
    "title": "services：Microservice 是 Agent 本体，也是部署边界",
    "vocabulary": VOCABULARY,
    "tree": TREE,
    "owns": ["Microservice", "Task"],
    "requirements": [
        "Microservice 是 Agent 本体，也是唯一部署边界。一个可部署的 worker 就是一个 Agent。",
        "Process、Execution、Thread 都不是可独立部署的单元；它们活在同一个 Agent 本体内。",
        "Microservice 收下 Task（用户/Agent 的目标），并为该目标创建 Process。",
        "Microservice 不调度。调度权属于 Process 资源上的 Scheduler。",
        "Task 是目标，不是 Work Unit，也不是可调度单元。一条 Task 不能当成一个 Execution。",
        "一次 Task 的多轮 Loop 发生在同一个 Process 内，不在部署边界上为每一轮再开一个 Agent。",
        "Event 不会在部署边界上变成新的 Agent 会话。",
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
