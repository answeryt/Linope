"""Forwards memory calls to kernel.scheduler."""

from kernel.scheduler.access import (
    address_scope,
    admit,
    keep_memory_system,
    latest_seq,
    memory_contents,
    memory_grant,
    memory_system,
    page_messages,
    remember,
    visible_classes,
)
from kernel.scheduler.memory_space import CLASSES

__all__ = [
    "CLASSES",
    "address_scope",
    "admit",
    "keep_memory_system",
    "latest_seq",
    "memory_contents",
    "memory_grant",
    "memory_system",
    "page_messages",
    "remember",
    "visible_classes",
]
