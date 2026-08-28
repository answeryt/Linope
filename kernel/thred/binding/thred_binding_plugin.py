# -*- coding: utf-8 -*-
"""Bind Thred resource requirements through an injected resource pool."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_thred_binding"
PLUGIN_VERSION = "1.0"


def build_binding(
    thred: Mapping[str, Any],
    process_id: str,
    binding_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(thred, Mapping):
        raise TypeError("thred must be a mapping")
    if not thred.get("name"):
        raise ValueError("thred is missing name")
    if not process_id:
        raise ValueError("process_id is required")
    return {
        "binding_id": binding_id or uuid4().hex,
        "process_id": str(process_id),
        "thred": dict(thred),
        "resource_leases": [],
        "state": "unbound",
    }


def _requirement(value: Any) -> tuple[str, int | float]:
    if isinstance(value, str):
        name, amount = value, 1
    elif isinstance(value, Mapping):
        name = value.get("resource_name", value.get("name"))
        amount = value.get("amount", 1)
    else:
        raise TypeError("resource requirements must be names or mappings")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("resource requirement is missing a name")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise TypeError("resource requirement amount must be an int or float")
    if amount <= 0:
        raise ValueError("resource requirement amount must be greater than zero")
    return name.strip(), amount


def _commit(
    binding: Mapping[str, Any], **changes: Any
) -> dict[str, Any]:
    if isinstance(binding, MutableMapping):
        binding.update(changes)
        return dict(binding)
    updated = dict(binding)
    updated.update(changes)
    return updated


async def bind_resources(
    binding: Mapping[str, Any],
    pool: Any,
    owner_id: str | None = None,
) -> dict[str, Any]:
    """Acquire all requirements atomically from the injected pool."""
    if pool is None or not callable(getattr(pool, "acquire", None)):
        raise TypeError("pool must provide acquire")
    if binding.get("state") == "bound":
        return dict(binding)
    thred = binding.get("thred")
    if not isinstance(thred, Mapping):
        raise ValueError("binding is missing its thred definition")

    owner = owner_id or binding.get("binding_id")
    if not owner:
        raise ValueError("owner_id or binding_id is required")
    leases: list[dict[str, Any]] = []
    try:
        for value in thred.get("requires") or ():
            name, amount = _requirement(value)
            lease = await pool.acquire(name, str(owner), amount)
            leases.append(dict(lease))
    except BaseException:
        for lease in reversed(leases):
            try:
                await pool.release(lease)
            except BaseException:
                pass
        _commit(binding, resource_leases=[], state="unbound")
        raise

    return _commit(binding, resource_leases=leases, state="bound")


async def release_resources(
    binding: Mapping[str, Any],
    pool: Any,
) -> dict[str, Any]:
    """Release recorded leases; repeated calls are harmless."""
    if pool is None or not callable(getattr(pool, "release", None)):
        raise TypeError("pool must provide release")
    if binding.get("state") == "released":
        return dict(binding)

    released: list[dict[str, Any]] = []
    for lease in binding.get("resource_leases") or ():
        released.append(dict(await pool.release(lease)))
    return _commit(binding, resource_leases=released, state="released")
