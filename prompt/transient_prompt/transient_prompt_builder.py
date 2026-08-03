"""Independent builder plugin for request-only transient prompt context.

"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class MemoryFormatter(Protocol):
    """Format raw memory recall before it enters the prompt."""

    def __call__(self, content: str) -> str:
        """Return a fenced or otherwise labelled memory block."""


class TransientPromptBuildError(RuntimeError):
    """Transient prompt assembly failed."""


def join_transient_context(
    parts: Sequence[str | None],
    *,
    separator: str = "\n\n",
) -> str:
    """Join non-empty transient fragments in deterministic source order."""

    if not separator:
        raise ValueError("separator must not be empty")
    return separator.join(
        part.strip() for part in parts if isinstance(part, str) and part.strip()
    )


@dataclass(frozen=True, slots=True)
class TransientPromptBuilderPlugin:
    """Compose one API-facing user message without mutating clean content."""

    name: str = "transient_user_context_builder"
    tier: str = "transient"
    priority: int = 100
    separator: str = "\n\n"

    def enabled(self, context: Mapping[str, Any] | None = None) -> bool:
        """Allow the host to disable transient injection for one request."""

        return bool((context or {}).get("build_transient_prompt", True))

    def render_memory(
        self,
        memory_context: str,
        formatter: MemoryFormatter | Callable[[str], str] | None = None,
    ) -> str:
        """Format memory recall, accepting a host-supplied fencing function."""

        if not isinstance(memory_context, str) or not memory_context.strip():
            return ""
        if formatter is None:
            return memory_context.strip()
        if not callable(formatter):
            raise TypeError("memory formatter must be callable")
        rendered = formatter(memory_context)
        if not isinstance(rendered, str):
            raise TransientPromptBuildError(
                "memory formatter must return a string"
            )
        return rendered.strip()

    def build_context(
        self,
        *,
        memory_context: str = "",
        plugin_context: str = "",
        gateway_context: str = "",
        memory_formatter: MemoryFormatter | Callable[[str], str] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        """Build only the transient suffix, preserving source order."""

        if not self.enabled(context):
            return ""
        memory_block = self.render_memory(memory_context, memory_formatter)
        return join_transient_context(
            (memory_block, plugin_context, gateway_context),
            separator=self.separator,
        )

    def compose_user_content(
        self,
        content: Any,
        *,
        memory_context: str = "",
        plugin_context: str = "",
        gateway_context: str = "",
        memory_formatter: MemoryFormatter | Callable[[str], str] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> str | None:
        """Return the API-facing user text, or ``None`` when not composable.

        A ``None`` result matches the existing sidecar contract: multimodal
        content or an empty transient suffix should be sent unchanged.
        """

        if not isinstance(content, str):
            return None
        suffix = self.build_context(
            memory_context=memory_context,
            plugin_context=plugin_context,
            gateway_context=gateway_context,
            memory_formatter=memory_formatter,
            context=context,
        )
        if not suffix:
            return None
        return content + self.separator + suffix

    def append_to_multimodal(self, content: Any, transient_text: str) -> bool:
        """Append must-deliver text to a multimodal content list in place."""

        if (
            not isinstance(content, list)
            or not isinstance(transient_text, str)
            or not transient_text.strip()
        ):
            return False
        content.append({"type": "text", "text": transient_text})
        return True


TRANSIENT_PROMPT_BUILDER_PLUGIN = TransientPromptBuilderPlugin()


def build_transient_prompt(
    content: Any,
    *,
    memory_context: str = "",
    plugin_context: str = "",
    gateway_context: str = "",
    memory_formatter: MemoryFormatter | Callable[[str], str] | None = None,
    context: Mapping[str, Any] | None = None,
) -> str | None:
    """Compose one transient API user message with the default plugin."""

    return TRANSIENT_PROMPT_BUILDER_PLUGIN.compose_user_content(
        content,
        memory_context=memory_context,
        plugin_context=plugin_context,
        gateway_context=gateway_context,
        memory_formatter=memory_formatter,
        context=context,
    )


__all__ = [
    "MemoryFormatter",
    "TRANSIENT_PROMPT_BUILDER_PLUGIN",
    "TransientPromptBuildError",
    "TransientPromptBuilderPlugin",
    "build_transient_prompt",
    "join_transient_context",
]
