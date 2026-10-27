"""Which command lines a page may offer right now.

A tool or model that is not up offers ``process start`` when this window can
launch a process. A tool that is up and sleeping offers ``load tool`` with its
pid filled in; a model that is up and sleeping offers ``ask`` with its pid
filled in. A busy one offers nothing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

from kernel.communication.page import CommandOffer

_OFFERED = ("tools.", "model.")


@lru_cache(maxsize=1)
def tool_catalog() -> tuple[str, ...]:
    """Every tool and model capability this checkout can start."""
    from kernel.process.process_creat.instances import discover_instances

    return tuple(sorted(name for name in discover_instances() if name.startswith(_OFFERED)))


@lru_cache(maxsize=None)
def tool_schema(capability: str) -> dict[str, Any]:
    """The parameters the tool declares, with its description. Empty when it declares none."""
    from kernel.process.process_manager.tool_dispatch import declared_tool_schema

    for schema in declared_tool_schema(capability):
        parameters = schema.get("parameters")
        found = dict(parameters) if isinstance(parameters, dict) else {}
        if schema.get("description"):
            found["description"] = str(schema["description"])
        return found
    return {}


def _permission(process: Any) -> tuple[str | None, Any]:
    """The asking model's permission and tool allow-list, when it has them."""
    activation = getattr(process, "activation", None)
    settings = getattr(activation, "settings", None)
    if not isinstance(settings, dict):
        settings = getattr(process, "settings", None)
    if not isinstance(settings, dict):
        return None, None
    permission = settings.get("permission")
    return (None if permission is None else str(permission), settings.get("capabilities"))


def command_offers(
    service: Any,
    asking: Any,
    *,
    catalog: Iterable[str] | None = None,
    schema: Any = None,
) -> tuple[CommandOffer, ...]:
    """The command links for the page of ``asking``."""
    schema = tool_schema if schema is None else schema
    from kernel.command.process.listen import (
        _capability_of,
        _pid_of,
        _processes,
        _record,
        _shown_activity,
    )

    permission, capabilities = _permission(asking)
    asking_pid = _pid_of(asking)
    can_start = callable(getattr(service, "launch", None))
    living: dict[str, list[Any]] = {}
    for process in _processes(service):
        if not getattr(process, "is_alive", False) or _pid_of(process) == asking_pid:
            continue
        name = _capability_of(process)
        if name.startswith(_OFFERED):
            living.setdefault(name, []).append(process)
    names = sorted(set(tool_catalog() if catalog is None else catalog) | set(living))
    offers: list[CommandOffer] = []
    from kernel.process.profiles import tool_allowed

    for name in names:
        if not tool_allowed(name, permission, capabilities):
            continue
        up = living.get(name) or []
        if not up:
            if can_start:
                offers.append(CommandOffer("start", name))
            continue
        idle = [
            process
            for process in up
            if _shown_activity(process, _record(process)) == "sleeping"
        ]
        if not idle:
            continue
        pid = min(_pid_of(process) for process in idle)
        if name.startswith("model."):
            offers.append(CommandOffer("ask", name, pid=pid))
        else:
            offers.append(CommandOffer("tool", name, pid=pid, schema=schema(name)))
    return tuple(offers)
