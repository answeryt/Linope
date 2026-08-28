"""Load lifecycle-aware composition Recipes from explicit paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .file_loader import FileModuleLoader


class RecipeLoader:
    """Load a Recipe by path; protocol validation remains in the Host loader."""

    def __init__(self, repo: Path) -> None:
        self._files = FileModuleLoader(repo)

    def load(self, name: str, path: str) -> Any:
        return self._files.load(
            "recipe",
            name,
            path,
            required=None,
        )

    def close(self) -> None:
        """Release Recipe modules loaded from disk."""
        self._files.close()
