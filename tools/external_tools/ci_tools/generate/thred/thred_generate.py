# -*- coding: utf-8 -*-
"""Write the thred-layer kernel architecture (wait context under Process).

Code-shape rules stay in ``generate/plugin``. This file only records the
architecture: Thread is not a Work Unit, not an OS thread, and not a deploy
boundary. The Process tree does not name Thread as a peer of Execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PLUGIN_NAME = "thred_architecture"
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
    "layer": "thred",
    "role": "wait_context",
    "title": "thred：Thread 是 Process 内的等待上下文，不是 Work Unit",
    "vocabulary": VOCABULARY,
    "tree": TREE,
    "owns": [],
    "note": "结构图不把 Thread 画成与 Process / Execution 平行的节点。Thread 附着在 Process 下，解释某个 Execution 为何等待。",
    "requirements": [
        "结构图不把 Thread 画成 Work Unit。Thread 不是第四种与 Process / Execution 平行的主体。",
        "Thread 是 Process 内部的等待与并发上下文，可以附着在某个 Execution 上。",
        "Thread 不是 OS thread，也不是部署边界。等待不占用内核线程。",
        "Thread 没有独立目标。目标属于 Task / Process。",
        "Scheduler 挑选的是 Execution，不是 Thread。Thread 只解释该 Execution 为何等待，或占用哪类资源。",
        "Process 结束时，其下 Thread 一并结束。",
        "Thread 不能替代 Process 的生命周期，也不能替代 Execution 的可调度性。",
    ],
}


def run(context: dict[str, Any]) -> dict[str, Any]:
    formats = _formats(context.get("format"))
    for fmt in formats:
        _emit(context, CARD_DIR / f"{LIST_STEM}.{fmt}", _render(ARCHITECTURE, fmt))
    return context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write thred architecture cards")
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
    lines.extend(["", "## 结构", "", "```", payload["tree"], "```", ""])
    note = payload.get("note")
    if note:
        lines.extend(["## 在结构图中的位置", "", note, ""])
    lines.extend(["## 本层拥有", ""])
    owns = payload.get("owns") or []
    if owns:
        for item in owns:
            lines.append(f"- `{item}`")
    else:
        lines.append("无。Thread 不是结构图上的独立节点。")
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
            if not value:
                lines.append("  []")
                continue
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
            if not value:
                lines.append(f"{key} = []")
                lines.append("")
                continue
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
