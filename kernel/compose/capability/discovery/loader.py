"""Create a resource container and inject capability classes onto the cap bus."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from kernel.compose.capability.assembly.context import ResourceContainer
from kernel.compose.capability.assembly.file_loader import FileModuleLoader
from kernel.compose.capability.negotiation.capabilities import CapabilityRegistry
from kernel.compose.capability.capability import Capability, inject, ordered_capability_types

_DEFAULT_REPO = Path(__file__).resolve().parents[3]


class CapabilityLoadError(RuntimeError):
    """Capability injection failed."""


def inject_capabilities(
    path: str | Path | None = None,
    *,
    repo: str | Path | None = None,
    capabilities: Sequence[type[Capability] | Capability] | None = None,
) -> ResourceContainer:
    """Create a resource container and inject capability classes."""
    if path is not None:
        given = Path(path)
        if given.suffix.lower() in {".yaml", ".yml", ".toml", ".json"}:
            raise CapabilityLoadError(
                "composition files are no longer supported; use class-based capabilities"
            )
    root = Path(repo) if repo is not None else _DEFAULT_REPO
    res = ResourceContainer(
        repo=root,
        files=FileModuleLoader(root),
        capabilities=CapabilityRegistry(lambda _name: None),
    )
    selected = _selected_types(capabilities)
    for plugin_cls in ordered_capability_types(selected):
        inject(plugin_cls(), res)
    return res


def kernel_capability_types() -> tuple[type[Capability], ...]:
    from kernel.compose.binding.compose_binding_plugin import ComposeBindingCapability
    from kernel.compose.definition.compose_definition_plugin import ComposeDefinitionCapability
    from kernel.compose.executor.compose_executor_plugin import ComposeExecutorCapability
    from kernel.compose.runtime.compose_runtime_plugin import ComposeRuntimeCapability

    return (
        ComposeDefinitionCapability,
        ComposeExecutorCapability,
        ComposeBindingCapability,
        ComposeRuntimeCapability,
    )


def _selected_types(
    capabilities: Sequence[type[Capability] | Capability] | None,
) -> tuple[type[Capability], ...]:
    if capabilities is None:
        return kernel_capability_types()
    result: list[type[Capability]] = []
    for item in capabilities:
        result.append(item if isinstance(item, type) else type(item))
    return tuple(result)
