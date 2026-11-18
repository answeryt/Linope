"""Types shared by the semantic action compiler and gateway."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CompletionKind = Literal["command", "turn", "session"]


@dataclass(frozen=True)
class EnvironmentDefaults:
    """Environment reference remembered by the connection gateway."""

    path: str = ""
    keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompiledAction:
    """One validated action represented as one or more kernel command lines."""

    action: str
    commands: tuple[str, ...]
    completion: CompletionKind
    environment_update: EnvironmentDefaults | None = None
