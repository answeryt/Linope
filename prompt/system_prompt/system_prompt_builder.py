"""Assemble system-prompt fragments supplied by an isolated loader plugin."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from .system_prompt_load import SYSTEM_PROMPT_PLUGIN


class SystemPromptPlugin(Protocol):
    """Minimal interface required by the prompt assembler."""

    def enabled(self, context: Mapping[str, Any] | None = None) -> bool:
        """Return whether this plugin should contribute prompt fragments."""

    def render(
        self,
        context: Mapping[str, Any] | None = None,
    ) -> tuple[str, ...]:
        """Return prompt fragments in assembly order."""


def build_system_prompt(
    context: Mapping[str, Any] | None = None,
    *,
    separator: str = "\n\n",
    plugin: SystemPromptPlugin = SYSTEM_PROMPT_PLUGIN,
) -> str:
    """Assemble all fragments supplied by a system-prompt plugin."""

    if not separator:
        raise ValueError("separator must not be empty")
    if not plugin.enabled(context):
        return ""
    return separator.join(
        fragment.strip()
        for fragment in plugin.render(context)
        if fragment and fragment.strip()
    )


def load_system_prompt(
    context: Mapping[str, Any] | None = None,
    *,
    separator: str = "\n\n",
) -> str:
    """Compatibility wrapper for the former public entry point."""

    return build_system_prompt(context, separator=separator)


__all__ = [
    "SystemPromptPlugin",
    "build_system_prompt",
    "load_system_prompt",
]
