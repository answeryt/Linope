"""Create operating-system processes for capability activations."""

from __future__ import annotations

from kernel.process.process_creat.strategy import launch_detached


class ProcessCreator:
    """Launch one capability process detached from this caller."""

    def __init__(self, store_locator: str) -> None:
        self._store_locator = str(store_locator)

    def spawn(self, process_id: str) -> int:
        """Start the process and return its pid. Do not wait or signal it."""
        return launch_detached(self._store_locator, process_id)
