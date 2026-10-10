"""Independent plugin for loading built-in Markdown system prompts.

The plugin owns filesystem discovery and reading only. Prompt assembly belongs
to ``system_prompt_builder``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class SystemPromptLoadError(RuntimeError):
    """Built-in system-prompt loading failed."""


def get_system_prompt_directory() -> Path:
    """Return the built-in prompt directory independently of the current cwd."""

    return Path(__file__).resolve().parents[2] / "prompt_card" / "system"


def load_system_prompt_files(prompt_directory: Path) -> tuple[str, ...]:
    """Read non-empty Markdown prompts in deterministic filename order."""

    if not isinstance(prompt_directory, Path):
        prompt_directory = Path(prompt_directory)
    if not prompt_directory.is_dir():
        raise SystemPromptLoadError(
            f"System prompt directory does not exist: {prompt_directory}"
        )

    prompt_files = sorted(
        (
            path
            for path in prompt_directory.iterdir()
            if path.is_file() and path.suffix.lower() == ".md"
        ),
        key=lambda path: path.name.casefold(),
    )

    prompts: list[str] = []
    for prompt_file in prompt_files:
        try:
            content = prompt_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise SystemPromptLoadError(
                f"Could not read system prompt file: {prompt_file}"
            ) from exc

        content = content.lstrip("\ufeff").strip()
        if content:
            prompts.append(content)

    if not prompts:
        raise SystemPromptLoadError(
            f"No non-empty Markdown system prompts found in: {prompt_directory}"
        )
    return tuple(prompts)


@dataclass(frozen=True, slots=True)
class MarkdownSystemPromptPlugin:
    """Plugin that supplies built-in Markdown prompt fragments."""

    name: str = "markdown_system_prompts"
    tier: str = "stable"
    priority: int = 0
    prompt_directory: Path = field(default_factory=get_system_prompt_directory)

    def enabled(self, context: Mapping[str, Any] | None = None) -> bool:
        """Allow a host to disable filesystem prompts explicitly."""

        return bool((context or {}).get("load_system_prompt_files", True))

    def render(
        self,
        context: Mapping[str, Any] | None = None,
    ) -> tuple[str, ...]:
        """Load and return prompt fragments for the builder."""

        del context
        return load_system_prompt_files(self.prompt_directory)


SYSTEM_PROMPT_PLUGIN = MarkdownSystemPromptPlugin()


__all__ = [
    "MarkdownSystemPromptPlugin",
    "SYSTEM_PROMPT_PLUGIN",
    "SystemPromptLoadError",
    "get_system_prompt_directory",
    "load_system_prompt_files",
]
