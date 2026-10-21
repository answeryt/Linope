"""Which command lines a page may offer right now.

A tool that is not up offers ``process start``. A tool that is up and sleeping
offers ``load tool`` with its pid filled in. A busy tool offers nothing.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable

from kernel.hypermedia.memory_page import CommandOffer


@lru_cache(maxsize=1)
def tool_catalog() -> tuple[str, ...]:
    """Every tool capability this checkout can start."""
    from kernel.process.process_creat.instances import discover_instances

    return tuple(sorted(name for name in discover_instances() if name.startswith("tools.")))


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

    asking_pid = _pid_of(asking)
    living: dict[str, list[Any]] = {}
    for process in _processes(service):
        if not getattr(process, "is_alive", False) or _pid_of(process) == asking_pid:
            continue
        name = _capability_of(process)
        if name.startswith("tools."):
            living.setdefault(name, []).append(process)
    names = sorted(set(tool_catalog() if catalog is None else catalog) | set(living))
    offers: list[CommandOffer] = []
    for name in names:
        up = living.get(name) or []
        if not up:
            offers.append(CommandOffer("start", name))
            continue
        idle = [
            process
            for process in up
            if _shown_activity(process, _record(process)) == "sleeping"
        ]
        if idle:
            pid = min(_pid_of(process) for process in idle)
            offers.append(CommandOffer("tool", name, pid=pid, schema=schema(name)))
    return tuple(offers)
