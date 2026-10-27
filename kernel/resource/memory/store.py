"""Write rows into a memory state. This module does not decide who may write."""

from __future__ import annotations

from typing import Any

from kernel.resource.memory.state import bump_seq, counters, items, now, prompt_sections


KIND_CLASS = {"user": "message", "model": "message", "tool": "artifact", "other": "task"}
STATES = ("asked", "continue", "resulted", "rejected", "answered")


def class_of(kind: str) -> str:
    if kind not in KIND_CLASS:
        raise ValueError(f"Unknown memory: {kind}")
    return KIND_CLASS[kind]


def append_row(state: dict[str, Any], kind: str, content: str, row_state: str = "") -> str:
    """Append one raw row. Returns its real name inside this memory."""

    if row_state and row_state not in STATES:
        raise ValueError(f"Unknown state: {row_state}")
    class_name = class_of(kind)
    stored = items(state)
    nxt = counters(state)
    real = f"{class_name}/{int(nxt.get(class_name) or 0)}"
    nxt[class_name] = int(nxt.get(class_name) or 0) + 1
    stored[real] = {
        "class": class_name,
        "kind": kind,
        "content": content,
        "time": now(),
        "seq": bump_seq(state),
    }
    if row_state:
        stored[real]["state"] = row_state
    state["items"] = stored
    state["next"] = nxt
    return real


def write_prompt(state: dict[str, Any], *, name: str, text: str, place: int | None = None) -> None:
    """Keep one prompt file and join every file into the system row."""

    label = str(name).strip()
    if not label:
        raise ValueError("Missing file")
    if place is not None and int(place) < 1:
        raise ValueError("Count starts at 1")
    sections = prompt_sections(state)
    index = next((i for i, item in enumerate(sections) if item["name"] == label), None)
    if index is not None:
        sections.pop(index)
    section = {"name": label, "content": text}
    if place is None and index is not None:
        sections.insert(index, section)
    elif place is None or int(place) - 1 >= len(sections):
        sections.append(section)
    else:
        sections.insert(int(place) - 1, section)
    joined = "\n\n".join(item["content"] for item in sections)
    stored = items(state)
    stored["system"] = {
        "class": "system",
        "kind": "system",
        "content": joined,
        "time": now(),
        "seq": bump_seq(state),
    }
    state["items"] = stored
    state["system"] = joined
    state["prompt_files"] = sections
