"""Compatibility entry. Resource routing is scheduled by ``kernel.scheduler``."""

from kernel.scheduler.route import route

__all__ = ["route"]
