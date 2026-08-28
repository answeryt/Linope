"""Create the local signal manager used by the Host facade."""

from __future__ import annotations

from typing import Any

from ..signals.manager import PluginManager


def create_event_manager() -> Any:
    return PluginManager("kernel_thred")
