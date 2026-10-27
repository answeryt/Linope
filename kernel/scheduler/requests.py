"""Typed steps a model may ask for. Parsing does not run them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel.communication.verify import Step


@dataclass(frozen=True)
class MemoryRead:
    """Read a selector inside a memory pointer. This is not a shell command."""

    selector: str


@dataclass(frozen=True)
class ActionCall:
    """Start a process, call a tool, or ask another model."""

    way: str
    pointer: str
    body: Any = None
    argv: tuple[str, ...] = ()
    pid: int = 0
    capability: str = ""


@dataclass(frozen=True)
class Answer:
    """The words that end the turn."""

    body: str


def classify(step: Step) -> MemoryRead | ActionCall | Answer:
    """Split one checked step into the only three things the scheduler runs."""

    if step.way == "read":
        return MemoryRead(step.pointer)
    if step.way == "answer":
        return Answer(str(step.body or ""))
    if step.way in {"start", "tool", "ask"}:
        return ActionCall(
            step.way,
            step.pointer,
            step.body,
            tuple(step.argv),
            int(step.pid),
            step.capability,
        )
    raise ValueError(f"Unknown step: {step.way}")
