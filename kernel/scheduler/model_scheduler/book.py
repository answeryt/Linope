"""The run queue for the model compute resource.

Ready means a task can use the model, using means it is using it now, and
waiting means it left to perform another operation such as a tool call.
"""

from __future__ import annotations

from collections import deque


class Book:
    """One shared task line for a configurable model core pool."""

    def __init__(self) -> None:
        self._ready: deque[str] = deque()
        self._using: dict[str, int] = {}
        self._waiting: set[str] = set()
        self._state: dict[str, str] = {}

    def state(self, key: str) -> str:
        return self._state.get(key, "")

    def known(self, key: str) -> bool:
        return key in self._state

    @property
    def model_busy(self) -> bool:
        return bool(self._using)

    def using_cores(self) -> tuple[int, ...]:
        """Return the core ids currently held by model tasks."""

        return tuple(self._using.values())

    def core_for(self, key: str) -> int | None:
        return self._using.get(key)

    def ready_keys(self) -> tuple[str, ...]:
        return tuple(self._ready)

    def peek_ready(self) -> str | None:
        return self._ready[0] if self._ready else None

    def admit(self, key: str) -> None:
        self._clear(key)
        self._state[key] = "ready"
        self._ready.append(key)

    def grant(self, core: int = 0, key: str | None = None) -> str | None:
        if core in self._using.values() or not self._ready:
            return None
        selected = self._ready[0] if key is None else key
        if selected not in self._ready:
            return None
        self._ready.remove(selected)
        self._using[selected] = int(core)
        self._state[selected] = "using_model"
        return selected

    def begin_wait(self, key: str) -> None:
        self._using.pop(key, None)
        self._ready = deque(item for item in self._ready if item != key)
        self._waiting.add(key)
        self._state[key] = "waiting"

    def finish_wait(self, key: str) -> None:
        self._waiting.discard(key)
        self._using.pop(key, None)
        self._ready = deque(item for item in self._ready if item != key)
        self._state[key] = "ready"
        self._ready.append(key)

    def finish(self, key: str) -> None:
        self._clear(key)

    def _clear(self, key: str) -> None:
        self._using.pop(key, None)
        self._waiting.discard(key)
        self._ready = deque(item for item in self._ready if item != key)
        self._state.pop(key, None)
