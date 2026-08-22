# -*- coding: utf-8 -*-
"""Per-process globals plus per-task locals for one agent run.

Inject this repo into the usecase. Do not confuse it with the context/
compression plugins; this is only the service-side bag.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, TypeVar


PLUGIN_NAME = "kernel_context_repo"
PLUGIN_VERSION = "1.0"

T = TypeVar("T")
_MISSING = object()


class ContextMissing(KeyError):
    """Raised when a required context key is not set."""


class ContextRepo:
    """Global process state plus task-scoped ContextVar storage."""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._global_context: dict[str, Any] = {"context": self, **(initial or {})}
        self._scope_context: dict[str, ContextVar[Any]] = {}

    @property
    def context(self) -> dict[str, Any]:
        return {
            **self._global_context,
            **{key: var.get() for key, var in self._scope_context.items()},
        }

    def set_global(self, key: str, value: Any) -> None:
        self._global_context[key] = value

    def reset_global(self, key: str) -> None:
        self._global_context.pop(key, None)

    def set_local(self, key: str, value: T) -> Token[T]:
        variable = self._scope_context.get(key)
        if variable is None:
            variable = ContextVar(key, default=_MISSING)
            self._scope_context[key] = variable
        return variable.set(value)

    def reset_local(self, key: str, tag: Token[Any]) -> None:
        self._scope_context[key].reset(tag)

    def get_local(self, key: str, default: Any = None) -> Any:
        variable = self._scope_context.get(key)
        if variable is None:
            return default
        value = variable.get()
        return default if value is _MISSING else value

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._global_context:
            return self._global_context[key]
        return self.get_local(key, default)

    def require(self, key: str) -> Any:
        value = self.get(key, _MISSING)
        if value is _MISSING:
            raise ContextMissing(key)
        return value

    @contextmanager
    def scope(self, key: str, value: Any) -> Generator[None, None, None]:
        token = self.set_local(key, value)
        try:
            yield
        finally:
            self.reset_local(key, token)

    def update_global(self, values: Mapping[str, Any]) -> None:
        self._global_context.update(values)
