"""One-shot prompt plugin for ``ephemeral_system_prompt``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import (
    TransientPromptBuilder,
    TransientPromptContext,
    TransientPromptRegistry,
)


@dataclass(frozen=True, slots=True)
class EphemeralSystemPromptPlugin:
    """Read and immediately clear the transient system prompt from the agent."""

    name: str = "ephemeral_system_prompt"
    priority: int = 100

    def enabled(self, context: TransientPromptContext) -> bool:
        agent = context.require("agent")
        value = getattr(agent, "ephemeral_system_prompt", None)
        return isinstance(value, str) and bool(value.strip())

    def consume(self, context: TransientPromptContext) -> str | None:
        agent = context.require("agent")
        value = getattr(agent, "ephemeral_system_prompt", None)

        # Clear before returning. If a later request build or send fails, the
        # prompt will not replay on the next independent request; retries for
        # the current request reuse the already-built message.
        agent.ephemeral_system_prompt = None

        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None


_registry = TransientPromptRegistry()
_registry.register(EphemeralSystemPromptPlugin())
_builder = TransientPromptBuilder(_registry)


def consume_ephemeral_system_prompt(agent: Any) -> str:
    """Consume any unused transient system prompt on the agent."""

    return _builder.consume({"agent": agent})


def merge_ephemeral_system_prompt(base_prompt: str | None, agent: Any) -> str:
    """Append the one-shot system prompt to the cached system prompt."""

    transient = consume_ephemeral_system_prompt(agent)
    return "\n\n".join(
        part.strip()
        for part in (base_prompt or "", transient)
        if part and part.strip()
    )


__all__ = [
    "EphemeralSystemPromptPlugin",
    "consume_ephemeral_system_prompt",
    "merge_ephemeral_system_prompt",
]
