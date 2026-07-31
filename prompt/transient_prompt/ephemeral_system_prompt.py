"""``ephemeral_system_prompt`` 的一次性提示词插件。"""

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
    """从 Agent 读取并立即清空临时系统提示词。"""

    name: str = "ephemeral_system_prompt"
    priority: int = 100

    def enabled(self, context: TransientPromptContext) -> bool:
        agent = context.require("agent")
        value = getattr(agent, "ephemeral_system_prompt", None)
        return isinstance(value, str) and bool(value.strip())

    def consume(self, context: TransientPromptContext) -> str | None:
        agent = context.require("agent")
        value = getattr(agent, "ephemeral_system_prompt", None)

        # 先清空再返回。这样即使后续请求构建或发送失败，该提示词也不会在
        # 下一个独立请求中意外重放；当前请求自身的重试会复用已构建消息。
        agent.ephemeral_system_prompt = None

        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None


_registry = TransientPromptRegistry()
_registry.register(EphemeralSystemPromptPlugin())
_builder = TransientPromptBuilder(_registry)


def consume_ephemeral_system_prompt(agent: Any) -> str:
    """消费 Agent 上尚未使用的临时系统提示词。"""

    return _builder.consume({"agent": agent})


def merge_ephemeral_system_prompt(base_prompt: str | None, agent: Any) -> str:
    """把一次性系统提示词合并到缓存系统提示词末尾。"""

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
