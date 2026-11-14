"""Which task may use the model resource.

Three lines of tasks. Ready means the task can ask. Using means it is asking
now. Waiting means it went off to read a file or to do some other wait.
A task is either a process's thread or another thread of that same process.
Switching them is the same step.
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
        if not self._ready:
            return None
        return self._ready[0]

    def admit(self, key: str) -> None:
        """Put a task at the back of the ready line."""

        self._clear(key)
        self._state[key] = "ready"
        self._ready.append(key)

    def grant(self, core: int = 0, key: str | None = None) -> str | None:
        """Give a free core to a ready task."""

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
        """This task left to wait. The model is free if it held it."""

        self._using.pop(key, None)
        self._ready = deque(item for item in self._ready if item != key)
        self._waiting.add(key)
        self._state[key] = "waiting"

    def finish_wait(self, key: str) -> None:
        """The wait is over. The task stands at the back of the ready line."""

        self._waiting.discard(key)
        self._using.pop(key, None)
        self._ready = deque(item for item in self._ready if item != key)
        self._state[key] = "ready"
        self._ready.append(key)

    def finish(self, key: str) -> None:
        """The task is done and leaves every line."""

        self._clear(key)

    def _clear(self, key: str) -> None:
        self._using.pop(key, None)
        self._waiting.discard(key)
        self._ready = deque(item for item in self._ready if item != key)
        self._state.pop(key, None)
