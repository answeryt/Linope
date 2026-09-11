"""Deterministic system-prompt truncation plugin.

System instructions are never summarized or rewritten by another model.
When a prompt exceeds its budget, the plugin keeps the beginning and end and
places an explicit omission marker between them, following the protected
head/tail strategy used by context compaction.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .system_prompt_parameters import (
    SystemPromptCompressionError,
    SystemPromptCompressionParameters,
)


@dataclass(frozen=True, slots=True)
class SystemPromptCompressionResult:
    """Diagnostics for one system-prompt compression operation."""

    content: str
    original_chars: int
    final_chars: int
    max_chars: int
    truncated: bool
    omitted_chars: int = 0


@dataclass(frozen=True, slots=True)
class SystemPromptCompressionPlugin:
    """Bound a system prompt while preserving its most useful boundaries."""

    parameters: SystemPromptCompressionParameters
    name: str = "system_prompt_head_tail_compression"
    priority: int = 200

    def enabled(self, context: Mapping[str, Any] | None = None) -> bool:
        """Allow callers to disable truncation for a particular build."""

        override = (context or {}).get("compress_system_prompt")
        if override is not None:
            if not isinstance(override, bool):
                raise SystemPromptCompressionError(
                    "compress_system_prompt must be a boolean"
                )
            return override
        return self.parameters.enabled

    def resolve_max_chars(self, context: Mapping[str, Any] | None = None) -> int:
        """Resolve an explicit budget or derive one from the context window."""

        values = context or {}
        explicit = values.get("system_prompt_max_chars")
        if explicit is not None:
            if isinstance(explicit, bool) or not isinstance(explicit, (int, float)):
                raise SystemPromptCompressionError(
                    "system_prompt_max_chars must be a positive number"
                )
            max_chars = int(explicit)
            if max_chars <= 0:
                raise SystemPromptCompressionError(
                    "system_prompt_max_chars must be a positive number"
                )
            return max_chars

        context_length = values.get("context_length")
        if (
            isinstance(context_length, int)
            and not isinstance(context_length, bool)
            and context_length > 0
        ):
            dynamic_budget = int(
                context_length
                * self.parameters.chars_per_token
                * self.parameters.context_window_fraction
            )
            return max(
                self.parameters.max_chars,
                min(dynamic_budget, self.parameters.max_dynamic_chars),
            )
        return self.parameters.max_chars

    def compress(
        self,
        prompt: str,
        context: Mapping[str, Any] | None = None,
    ) -> str:
        """Return the bounded prompt text."""

        return self.compress_result(prompt, context).content

    def compress_result(
        self,
        prompt: str,
        context: Mapping[str, Any] | None = None,
    ) -> SystemPromptCompressionResult:
        """Compress a prompt and return content plus truncation diagnostics."""

        if not isinstance(prompt, str):
            raise TypeError("prompt must be a string")

        max_chars = self.resolve_max_chars(context)
        original_chars = len(prompt)
        if not self.enabled(context) or original_chars <= max_chars:
            return SystemPromptCompressionResult(
                content=prompt,
                original_chars=original_chars,
                final_chars=original_chars,
                max_chars=max_chars,
                truncated=False,
            )

        marker = (
            "\n\n[... system prompt truncated: protected beginning and end; "
            "middle instructions omitted ...]\n\n"
        )
        if len(marker) >= max_chars:
            content = marker[:max_chars]
            return SystemPromptCompressionResult(
                content=content,
                original_chars=original_chars,
                final_chars=len(content),
                max_chars=max_chars,
                truncated=True,
                omitted_chars=original_chars,
            )

        retained_budget = max_chars - len(marker)
        ratio_total = self.parameters.head_ratio + self.parameters.tail_ratio
        head_chars = int(retained_budget * self.parameters.head_ratio / ratio_total)
        tail_chars = retained_budget - head_chars
        omitted_chars = original_chars - head_chars - tail_chars
        tail = prompt[-tail_chars:] if tail_chars else ""
        content = prompt[:head_chars] + marker + tail

        return SystemPromptCompressionResult(
            content=content,
            original_chars=original_chars,
            final_chars=len(content),
            max_chars=max_chars,
            truncated=True,
            omitted_chars=omitted_chars,
        )


def compress_system_prompt(
    prompt: str,
    parameters: SystemPromptCompressionParameters,
    context: Mapping[str, Any] | None = None,
) -> str:
    """Compress a system prompt using explicitly supplied validated parameters."""

    return SystemPromptCompressionPlugin(parameters=parameters).compress(prompt, context)


__all__ = [
    "SystemPromptCompressionError",
    "SystemPromptCompressionPlugin",
    "SystemPromptCompressionResult",
    "compress_system_prompt",
]
