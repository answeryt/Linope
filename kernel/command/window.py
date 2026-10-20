"""The one living window, when a command is running inside it."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

_window: ContextVar[Any] = ContextVar("linope_window", default=None)
_line: ContextVar[str] = ContextVar("linope_line", default="")


def current_window() -> Any:
    """The clerk that is reading lines, or none for a one-shot command."""
    return _window.get()


def current_line() -> str:
    """The line the window just read."""
    return _line.get()


def bind_window(window: Any) -> Any:
    return _window.set(window)


def reset_window(token: Any) -> None:
    _window.reset(token)


def bind_line(line: str) -> Any:
    return _line.set(line)


def reset_line(token: Any) -> None:
    _line.reset(token)
