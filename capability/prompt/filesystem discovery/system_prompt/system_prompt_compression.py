"""Deterministic system-prompt truncation plugin.

System instructions are never summarized or rewritten by another model.
When a prompt exceeds its budget, the plugin keeps the beginning and end and
places an explicit omission marker between them, following the protected
head/tail strategy used by context compaction.

Parameters are an injected mapping. This leaf does not import the parameter-card
loader.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class SystemPromptCompressionError(RuntimeError):
    """System-prompt compression configuration or execution failed."""


@dataclass(frozen=True, slots=True)
class SystemPromptCompressionResult:
    """Diagnostics for one system-prompt compression operation."""

    content: str
    original_chars: int
    final_chars: int
    max_chars: int
    truncated: bool
    omitted_chars: int = 0


def _resolved_parameters(parameters: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "enabled",
        "max_chars",
        "chars_per_token",
        "context_window_fraction",
        "max_dynamic_chars",
        "head_ratio",
        "tail_ratio",
    }
    unknown = set(parameters) - expected
    missing = expected - set(parameters)
    if unknown:
        raise SystemPromptCompressionError(
            f"Unknown compression parameters: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise SystemPromptCompressionError(
            f"Missing compression parameters: {', '.join(sorted(missing))}"
        )
    values = dict(parameters)

    if not isinstance(values["enabled"], bool):
        raise SystemPromptCompressionError("enabled must be a boolean")
    for name in ("max_chars", "chars_per_token", "max_dynamic_chars"):
        value = values[name]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise SystemPromptCompressionError(
                f"{name} must be a positive integer"
            )
    if values["max_dynamic_chars"] < values["max_chars"]:
        raise SystemPromptCompressionError(
            "max_dynamic_chars must not be below max_chars"
        )
    fraction = values["context_window_fraction"]
    if (
        isinstance(fraction, bool)
        or not isinstance(fraction, (int, float))
        or not 0 < fraction <= 1
    ):
        raise SystemPromptCompressionError(
            "context_window_fraction must be a number in (0, 1]"
        )
    for name in ("head_ratio", "tail_ratio"):
        ratio = values[name]
        if (
            isinstance(ratio, bool)
            or not isinstance(ratio, (int, float))
            or ratio < 0
        ):
            raise SystemPromptCompressionError(
                f"{name} must be a non-negative number"
            )
    if values["head_ratio"] + values["tail_ratio"] <= 0:
        raise SystemPromptCompressionError(
            "at least one retention ratio must be positive"
        )
    return values


@dataclass(frozen=True, slots=True)
class SystemPromptCompressionPlugin:
    """Bound a system prompt while preserving its most useful boundaries."""

    parameters: Mapping[str, Any]
    name: str = "system_prompt_head_tail_compression"
    priority: int = 200
    omission_marker: str = (
        "\n\n[... system prompt truncated: protected beginning and end; "
        "middle instructions omitted ...]\n\n"
    )

    def _parameters(
        self,
        context: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        overrides = (context or {}).get("system_prompt_parameters")
        if overrides is not None and not isinstance(overrides, Mapping):
            raise SystemPromptCompressionError(
                "system_prompt_parameters must be a mapping"
            )
        values = dict(self.parameters)
        if overrides:
            values.update(overrides)
        return _resolved_parameters(values)

    def enabled(self, context: Mapping[str, Any] | None = None) -> bool:
        """Allow callers to disable truncation for a particular build."""

        override = (context or {}).get("compress_system_prompt")
        if override is not None:
            if not isinstance(override, bool):
                raise SystemPromptCompressionError(
                    "compress_system_prompt must be a boolean"
                )
            return override
        return bool(self._parameters(context)["enabled"])

    def resolve_max_chars(self, context: Mapping[str, Any] | None = None) -> int:
        """Resolve an explicit budget or derive one from the context window."""

        values = context or {}
        parameters = self._parameters(context)
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
                * parameters["chars_per_token"]
                * parameters["context_window_fraction"]
            )
            return max(
                parameters["max_chars"],
                min(dynamic_budget, parameters["max_dynamic_chars"]),
            )
        return int(parameters["max_chars"])

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

        marker = self.omission_marker
        if not isinstance(marker, str) or not marker:
            raise SystemPromptCompressionError(
                "omission_marker must be a non-empty string"
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

        parameters = self._parameters(context)
        retained_budget = max_chars - len(marker)
        ratio_total = parameters["head_ratio"] + parameters["tail_ratio"]
        head_chars = int(retained_budget * parameters["head_ratio"] / ratio_total)
        tail_chars = retained_budget - head_chars
        tail = prompt[-tail_chars:] if tail_chars else ""
        content = prompt[:head_chars] + marker + tail

        return SystemPromptCompressionResult(
            content=content,
            original_chars=original_chars,
            final_chars=len(content),
            max_chars=max_chars,
            truncated=True,
            omitted_chars=original_chars - head_chars - tail_chars,
        )


def compress_system_prompt(
    prompt: str,
    parameters: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> str:
    """Compress a system prompt using an injected parameter mapping."""

    return SystemPromptCompressionPlugin(parameters=parameters).compress(prompt, context)


__all__ = [
    "SystemPromptCompressionError",
    "SystemPromptCompressionPlugin",
    "SystemPromptCompressionResult",
    "compress_system_prompt",
]
