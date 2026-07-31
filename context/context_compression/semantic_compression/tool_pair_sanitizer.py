"""Sanitize orphaned tool-call/tool-result pairs."""

from __future__ import annotations

from typing import Any


def sanitize_tool_pairs(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove orphan results and strip calls without matching results."""
    call_ids: set[str] = set()
    result_ids: set[str] = set()
    for message in messages:
        if message.get("role") == "assistant":
            for call in message.get("tool_calls") or []:
                if isinstance(call, dict):
                    call_id = str(call.get("call_id") or call.get("id") or "")
                    if call_id:
                        call_ids.add(call_id)
        elif message.get("role") == "tool":
            call_id = str(message.get("tool_call_id") or "")
            if call_id:
                result_ids.add(call_id)

    orphan_results = result_ids - call_ids
    missing_results = call_ids - result_ids
    if not orphan_results and not missing_results:
        return messages

    output: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "tool" and str(message.get("tool_call_id") or "") in orphan_results:
            continue
        if message.get("role") != "assistant" or not message.get("tool_calls"):
            output.append(message)
            continue
        kept = [
            call for call in message["tool_calls"]
            if not isinstance(call, dict)
            or str(call.get("call_id") or call.get("id") or "") not in missing_results
        ]
        if len(kept) == len(message["tool_calls"]):
            output.append(message)
            continue
        replacement = dict(message)
        if kept:
            replacement["tool_calls"] = kept
        else:
            replacement.pop("tool_calls", None)
            content = replacement.get("content")
            if not content or (isinstance(content, str) and not content.strip()):
                replacement["content"] = "(tool call removed)"
        output.append(replacement)
    return output
