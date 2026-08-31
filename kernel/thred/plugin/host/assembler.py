"""Load descriptors and mount them through the universal plugin contract."""

from __future__ import annotations

import importlib.metadata
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .bridges import bridge_plugin
from .contracts import ArtifactSource, PluginDescriptor, PluginState
from .fiber import Fiber
from .services import install_core_services


class AssemblyError(RuntimeError):
    """Discovered artifacts could not form a valid live composition."""


class Assembler:
    """Join discovery sources to the Host without coupling either side."""

    def __init__(self, context: Any, *, install_services: bool = True) -> None:
        self.context = context
        self._services_installed = False
        if install_services:
            self.install_services()

    def install_services(self) -> None:
        if self._services_installed:
            return
        names = (
            "tools",
            "llm",
            "pipelines",
            "prompt",
            "compression",
            "sandbox",
            "mcp",
            "ui",
        )
        if all(self.context.has_service(name) for name in names):
            self._services_installed = True
            return
        scoped = self.context.bind("__plugin_services__")
        install_core_services(scoped)
        self._services_installed = True

    def mount_source(
        self,
        source: ArtifactSource,
        *,
        strict: bool = False,
    ) -> tuple[Fiber, ...]:
        return self.mount(source.discover(), strict=strict)

    def mount(
        self,
        descriptors: Iterable[PluginDescriptor],
        *,
        strict: bool = False,
    ) -> tuple[Fiber, ...]:
        mounted: list[Fiber] = []
        identities: set[tuple[str, str]] = set()
        for descriptor in descriptors:
            identity = (
                descriptor.artifact.name,
                descriptor.artifact.version,
            )
            if identity in identities:
                raise AssemblyError(f"duplicate artifact identity: {identity!r}")
            identities.add(identity)
            try:
                loaded = self._load(descriptor)
                installer = bridge_plugin(loaded, descriptor)
                mounted.append(
                    self.context.plugin(
                        installer,
                        descriptor.config,
                        name=descriptor.artifact.name,
                        version=descriptor.artifact.version,
                        requirements=descriptor.requirements,
                        source=descriptor.artifact.source,
                        kind=descriptor.artifact.kind,
                    )
                )
            except Exception as error:
                raise AssemblyError(
                    f"cannot mount plugin {descriptor.artifact.name!r}: {error}"
                ) from error
        if strict:
            failed = [
                fiber.name
                for fiber in mounted
                if fiber.state is PluginState.FAILED
            ]
            pending = {
                fiber.name: fiber.missing
                for fiber in mounted
                if fiber.state is PluginState.PENDING
            }
            if failed or pending:
                for fiber in reversed(mounted):
                    fiber.dispose()
                detail = []
                if failed:
                    detail.append(f"failed={failed!r}")
                if pending:
                    detail.append(f"pending={pending!r}")
                raise AssemblyError("unsatisfied composition: " + ", ".join(detail))
        return tuple(mounted)

    def _load(self, descriptor: PluginDescriptor) -> Any:
        artifact = descriptor.artifact
        if artifact.kind == "entry_point" or artifact.source.startswith("entrypoint:"):
            return _load_entry_point(artifact.source)
        if not artifact.source:
            raise ValueError("file-backed artifacts require a source path")
        return self.context._runtime.recipes.load(
            artifact.name,
            artifact.source,
        )


def _load_entry_point(source: str) -> Any:
    try:
        prefix, group, name = source.split(":", 2)
    except ValueError as error:
        raise ValueError(f"invalid entry point source: {source!r}") from error
    if prefix != "entrypoint":
        raise ValueError(f"invalid entry point source: {source!r}")
    matches = [
        entry
        for entry in importlib.metadata.entry_points(group=group)
        if entry.name == name
    ]
    if len(matches) != 1:
        raise LookupError(
            f"expected one entry point {group}:{name}, found {len(matches)}"
        )
    return matches[0].load()
