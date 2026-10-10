"""Independent loader plugin for built-in transient Markdown prompts.

Filesystem discovery and reading live here; assembly, caching, compression, and
parameter parsing remain responsibilities of separately registered plugins.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class TransientPromptLoadError(RuntimeError):
    """Built-in transient-prompt loading failed."""


def get_transient_prompt_directory() -> Path:
    """Return the transient prompt-card directory independently of cwd."""

    return Path(__file__).resolve().parents[2] / "prompt_card" / "transient"


def load_transient_prompt_files(prompt_directory: Path) -> tuple[str, ...]:
    """Read non-empty Markdown fragments in deterministic filename order."""

    if not isinstance(prompt_directory, Path):
        prompt_directory = Path(prompt_directory)
    if not prompt_directory.is_dir():
        raise TransientPromptLoadError(
            f"Transient prompt directory does not exist: {prompt_directory}"
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
            raise TransientPromptLoadError(
                f"Could not read transient prompt file: {prompt_file}"
            ) from exc
        content = content.lstrip("\ufeff").strip()
        if content:
            prompts.append(content)

    if not prompts:
        raise TransientPromptLoadError(
            f"No non-empty Markdown transient prompts found in: {prompt_directory}"
        )
    return tuple(prompts)


@dataclass(frozen=True, slots=True)
class MarkdownTransientPromptPlugin:
    """Supply request-only Markdown prompt fragments."""

    name: str = "markdown_transient_prompts"
    tier: str = "transient"
    priority: int = 0
    prompt_directory: Path = field(
        default_factory=get_transient_prompt_directory
    )

    def enabled(self, context: Mapping[str, Any] | None = None) -> bool:
        """Allow a host to disable filesystem transient prompts."""

        return bool((context or {}).get("load_transient_prompt_files", True))

    def render(
        self,
        context: Mapping[str, Any] | None = None,
    ) -> tuple[str, ...]:
        """Load fragments without assembling or transforming them."""

        if not self.enabled(context):
            return ()
        return load_transient_prompt_files(self.prompt_directory)


TRANSIENT_PROMPT_LOAD_PLUGIN = MarkdownTransientPromptPlugin()


def load_transient_prompts(
    context: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    """Load built-in transient fragments with the default plugin."""

    return TRANSIENT_PROMPT_LOAD_PLUGIN.render(context)


__all__ = [
    "MarkdownTransientPromptPlugin",
    "TRANSIENT_PROMPT_LOAD_PLUGIN",
    "TransientPromptLoadError",
    "get_transient_prompt_directory",
    "load_transient_prompt_files",
    "load_transient_prompts",
]
