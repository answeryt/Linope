"""One-line summaries for completed tool results."""

from __future__ import annotations

import json
import re
from typing import Any, Callable


SummaryCallback = Callable[[str, str, str], str]


def _text(value: Any, default: str = "") -> str:
    return value if isinstance(value, str) else (str(value) if value is not None else default)


def default_tool_result_summary(tool_name: str, tool_args: str, content: str) -> str:
    """Summarize common tools and always return a safe one-line fallback."""
    try:
        parsed = json.loads(tool_args) if tool_args else {}
        args = parsed if isinstance(parsed, dict) else {}
        size = len(content)
        lines = content.count("\n") + 1 if content.strip() else 0
        if tool_name in {"terminal", "shell"}:
            command = _text(args.get("command"))[:80]
            match = re.search(r'"exit_code"\s*:\s*(-?\d+)', content)
            return f"[{tool_name}] ran `{command}` -> exit {match.group(1) if match else '?'}, {lines} lines"
        if tool_name in {"read_file", "ReadFile"}:
            return f"[{tool_name}] read {args.get('path', '?')} from line {args.get('offset', 1)} ({size:,} chars)"
        if tool_name in {"write_file", "patch", "ApplyPatch"}:
            return f"[{tool_name}] changed {args.get('path', '?')} ({size:,} chars result)"
        if tool_name in {"search_files", "rg", "Glob"}:
            query = args.get("pattern", args.get("glob_pattern", "?"))
            return f"[{tool_name}] searched for {query!r} in {args.get('path', '.')} ({size:,} chars result)"
        if tool_name.startswith("browser_"):
            detail = args.get("url") or args.get("ref") or ""
            return f"[{tool_name}] {_text(detail)[:100]} ({size:,} chars result)".replace("]  (", "] (")
        if tool_name in {"web_search", "WebSearch"}:
            return f"[{tool_name}] query={args.get('query', args.get('search_term', '?'))!r} ({size:,} chars result)"
        if tool_name in {"web_extract", "WebFetch"}:
            return f"[{tool_name}] fetched {args.get('url', args.get('urls', '?'))!s} ({size:,} chars result)"
        if tool_name in {"execute_code", "delegate_task", "Subagent"}:
            detail = _text(args.get("code", args.get("goal", args.get("prompt", "")))).replace("\n", " ")[:60]
            return f"[{tool_name}] {detail!r} ({size:,} chars result)"
        if tool_name == "skill_view":
            return f"[skill_view] name={args.get('name', '?')} ({size:,} chars)"
        if tool_name in {"vision_analyze", "memory", "todo", "clarify", "process", "cronjob"}:
            detail = " ".join(f"{key}={_text(value)[:40]}" for key, value in list(args.items())[:2])
            return f"[{tool_name}] {detail} ({size:,} chars result)".replace("]  (", "] (")
        detail = " ".join(f"{key}={_text(value)[:40]}" for key, value in list(args.items())[:2])
        return f"[{tool_name or 'unknown'}] {detail} ({size:,} chars result)".replace("]  (", "] (")
    except Exception:
        safe_name = tool_name if isinstance(tool_name, str) and tool_name else "unknown"
        return f"[{safe_name}] ({len(content) if isinstance(content, str) else 0:,} chars result)"


def summarize_tool_results(
    messages: list[dict[str, Any]],
    *,
    should_summarize: Callable[[int, dict[str, Any]], bool],
    summary_callback: SummaryCallback = default_tool_result_summary,
) -> list[dict[str, Any]]:
    """Replace selected string tool results; selection policy is Host-owned."""
    calls: dict[str, tuple[str, str]] = {}
    for message in messages:
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            function = call.get("function") if isinstance(call.get("function"), dict) else {}
            call_id = str(call.get("call_id") or call.get("id") or "")
            if call_id:
                calls[call_id] = (_text(function.get("name"), "unknown"), _text(function.get("arguments")))
    result = list(messages)
    changed = False
    for index, message in enumerate(messages):
        content = message.get("content")
        if message.get("role") != "tool" or not isinstance(content, str) or not should_summarize(index, message):
            continue
        name, args = calls.get(str(message.get("tool_call_id") or ""), ("unknown", ""))
        result[index] = {**message, "content": summary_callback(name, args, content)}
        changed = True
    return result if changed else messages
