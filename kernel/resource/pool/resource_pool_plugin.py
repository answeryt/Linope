# -*- coding: utf-8 -*-
"""In-memory accounting for Host-defined resources and leases."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4


PLUGIN_NAME = "kernel_resource_pool"
PLUGIN_VERSION = "1.0"


class ResourceCapacityError(RuntimeError):
    """Raised when a resource cannot satisfy an acquisition."""


async def _call_hook(
    hook: Callable[..., Any] | None, lease: Mapping[str, Any]
) -> Any:
    if hook is None:
        return None
    result = hook(dict(lease))
    if inspect.isawaitable(result):
        return await result
    return result


class ResourcePool:
    """Register resource mappings and account for their active leases."""

    def __init__(self) -> None:
        self._resources: dict[str, dict[str, Any]] = {}
        self._leases: dict[str, dict[str, Any]] = {}

    def register(self, resource: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(resource, Mapping):
            raise TypeError("resource must be a mapping")
        name = resource.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("resource is missing a non-empty name")
        capacity = resource.get("capacity")
        if isinstance(capacity, bool) or (
            capacity is not None and not isinstance(capacity, (int, float))
        ):
            raise TypeError("capacity must be an int, float, or None")
        if capacity is not None and capacity < 0:
            raise ValueError("capacity must be non-negative")
        stored = dict(resource)
        stored["name"] = name.strip()
        self._resources[stored["name"]] = stored
        return dict(stored)

    def require(self, name: str) -> dict[str, Any]:
        try:
            return dict(self._resources[str(name)])
        except KeyError:
            raise KeyError(name) from None

    def can_acquire(
        self,
        requirements: Mapping[str, int | float]
        | list[str | Mapping[str, Any]]
        | tuple[str | Mapping[str, Any], ...],
    ) -> bool:
        """Return whether all requested amounts fit without changing capacity."""
        requested: dict[str, int | float] = {}
        items = (
            requirements.items()
            if isinstance(requirements, Mapping)
            else (
                (
                    str(item.get("name") or item.get("resource_name") or ""),
                    item.get("amount", 1),
                )
                if isinstance(item, Mapping)
                else (str(item), 1)
                for item in requirements
            )
        )
        for name, amount in items:
            resource = self.require(str(name))
            requested[str(name)] = requested.get(str(name), 0) + amount
            capacity = resource.get("capacity")
            if not resource.get("shareable", True) and (
                self._allocated(str(name)) > 0 or requested[str(name)] > amount
            ):
                return False
            if (
                capacity is not None
                and self._allocated(str(name)) + requested[str(name)] > capacity
            ):
                return False
        return True

    @staticmethod
    def is_capacity_error(error: BaseException) -> bool:
        return isinstance(error, ResourceCapacityError)

    async def acquire(
        self,
        resource_name: str,
        owner_id: str,
        amount: int | float = 1,
    ) -> dict[str, Any]:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise TypeError("amount must be an int or float")
        if amount <= 0:
            raise ValueError("amount must be greater than zero")
        resource = self.require(resource_name)

        capacity = resource.get("capacity")
        allocated = self._allocated(resource_name)
        if not resource.get("shareable", True) and allocated > 0:
            raise ResourceCapacityError(f"{resource_name!r} is not shareable")
        if capacity is not None and allocated + amount > capacity:
            raise ResourceCapacityError(
                f"{resource_name!r} capacity {capacity} cannot satisfy {amount}"
            )
        lease = {
            "lease_id": uuid4().hex,
            "resource_name": str(resource_name),
            "owner_id": str(owner_id),
            "amount": amount,
            "state": "acquired",
        }
        self._leases[lease["lease_id"]] = lease

        try:
            await _call_hook(resource.get("acquire"), lease)
        except BaseException:
            self._leases.pop(lease["lease_id"], None)
            raise
        return dict(lease)

    async def release(
        self, lease: str | Mapping[str, Any]
    ) -> dict[str, Any]:
        lease_id = (
            lease.get("lease_id") if isinstance(lease, Mapping) else lease
        )
        if not lease_id:
            raise ValueError("lease is missing lease_id")

        stored = self._leases.get(str(lease_id))
        if stored is None:
            raise KeyError(lease_id)
        if stored["state"] == "released":
            return dict(stored)
        stored["state"] = "released"
        released = dict(stored)

        resource = self.require(str(released["resource_name"]))
        await _call_hook(resource.get("release"), released)
        return released

    def snapshot(self) -> dict[str, Any]:
        resources: dict[str, dict[str, Any]] = {}
        for name, resource in self._resources.items():
            capacity = resource.get("capacity")
            allocated = self._allocated(name)
            resources[name] = {
                **dict(resource),
                "allocated": allocated,
                "available": None if capacity is None else capacity - allocated,
            }
        return {
            "resources": resources,
            "leases": {
                lease_id: dict(lease)
                for lease_id, lease in self._leases.items()
            },
        }

    def _allocated(self, resource_name: str) -> int | float:
        return sum(
            lease["amount"]
            for lease in self._leases.values()
            if lease["resource_name"] == str(resource_name)
            and lease["state"] == "acquired"
        )


def compose_resources(*resources: Mapping[str, Any]) -> ResourcePool:
    """Build one finite pool from user-composed resource definitions."""
    pool = ResourcePool()
    for resource in resources:
        pool.register(resource)
    return pool
