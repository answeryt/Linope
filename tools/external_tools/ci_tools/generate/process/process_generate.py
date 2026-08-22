# -*- coding: utf-8 -*-
"""Write the process-layer kernel architecture (Process / State / Resources / Memory).

Code-shape rules stay in ``generate/plugin``. This file only records the
architecture: a Process is the Work Unit, not an OS process and not a deploy unit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PLUGIN_NAME = "process_architecture"
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
    "layer": "process",
    "role": "work_unit",
    "title": "process：Process 是带目标的 Agent Work Unit",
    "vocabulary": VOCABULARY,
    "tree": TREE,
    "owns": ["Process", "State", "Resources", "Memory"],
    "requirements": [
        "Process 是 Agent Work Unit：必须有独立目标、状态、资源和生命周期。",
        "目标来自 Task。Process 是该目标的运行时实体，不是第二条用户目标。",
        "Process 持有 State、Resources、Memory。这三者属于 Process，不属于单个 Execution。",
        "Scheduler 从 Resources 长出：先有 Process 的资源，再把可调度权切给 Execution。",
        "Process 不执行。执行只发生在 Scheduler 选出的 Execution 上。",
        "一个 Process 下可以同时存在多个 Execution，分别使用 Agent Loop、Tool Loop、Event Loop。",
        "Process 结束时，其下全部 Execution 一并结束。",
        "State 描述这个 Work Unit 是否还活着；它不是 Execution 的 run/wait，也不是部署进程的起停。",
    ],
}


def run(context: dict[str, Any]) -> dict[str, Any]:
    formats = _formats(context.get("format"))
    for fmt in formats:
        _emit(context, CARD_DIR / f"{LIST_STEM}.{fmt}", _render(ARCHITECTURE, fmt))
    return context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write process architecture cards")
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
