# -*- coding: utf-8 -*-
"""Resource limits on an Agent Process mapping (tokens, steps, seconds).

Host injects consume/check into the scheduler or dispatch. This plugin
does not import PCB or table siblings.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any


PLUGIN_NAME = "kernel_process_budget"
PLUGIN_VERSION = "1.0"

BUDGET = "budget"
TOKENS = "tokens"
STEPS = "steps"
SECONDS = "seconds"


class BudgetExhausted(RuntimeError):
    """Raised when a process has no remaining budget for a resource."""


def remaining(record: Mapping[str, Any], resource: str = TOKENS) -> float:
    budget = record.get(BUDGET)
    if not isinstance(budget, Mapping):
        return 0.0
    value = budget.get(resource, 0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def exhausted(record: Mapping[str, Any], resource: str = TOKENS) -> bool:
    return remaining(record, resource) <= 0


def consume(
    record: Mapping[str, Any],
    amount: float,
    resource: str = TOKENS,
    *,
    raise_if_empty: bool = True,
) -> dict[str, Any]:
    """Return a copy with ``amount`` subtracted. Does not mutate ``record``."""
    if amount < 0:
        raise ValueError("amount must be non-negative")
    left = remaining(record, resource)
    if left < amount:
        if raise_if_empty:
            raise BudgetExhausted(resource)
        amount = left
    budget: MutableMapping[str, Any] = dict(record.get(BUDGET) or {})
    budget[resource] = left - amount
    updated = dict(record)
    updated[BUDGET] = dict(budget)
    return updated
