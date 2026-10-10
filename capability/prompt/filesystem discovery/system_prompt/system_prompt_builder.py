"""Assemble system-prompt fragments supplied by an injected loader plugin.

This leaf does not import the filesystem loader. Host or runtime must inject a
plugin that satisfies ``SystemPromptPlugin``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


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
    plugin: SystemPromptPlugin | None = None,
) -> str:
    """Assemble fragments from an injected plugin.

    ``plugin`` is required for a non-empty result. Omitting it returns ``""``
    so this leaf never reaches into the loader.
    """

    if not separator:
        raise ValueError("separator must not be empty")
    if plugin is None or not plugin.enabled(context):
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
    plugin: SystemPromptPlugin | None = None,
) -> str:
    """Compatibility wrapper for the former public entry point."""

    return build_system_prompt(context, separator=separator, plugin=plugin)


__all__ = [
    "SystemPromptPlugin",
    "build_system_prompt",
    "load_system_prompt",
]
