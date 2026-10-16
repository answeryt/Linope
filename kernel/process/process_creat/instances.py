"""Stable ids for complete capability instances."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from kernel.resource.definition import ResourceDefinition


@dataclass(frozen=True)
class CapabilityDefinition:
    """Serializable description of one loadable capability instance."""

    instance_id: str
    module_paths: tuple[str, ...]
    entrypoint: str | None = None
    resource_requirements: tuple[ResourceDefinition, ...] = ()

    def activation(self) -> dict[str, Any]:
        """Build the definition payload passed to a capability process."""
        return {
            "instance_id": self.instance_id,
            "module_paths": self.module_paths,
            "entrypoint": self.entrypoint,
            "resource_requirements": [
                {
                    "kind": requirement.kind.value,
                    "required": requirement.required,
                    "share_mode": requirement.share_mode.value,
                    "limits": dict(requirement.limits),
                }
                for requirement in self.resource_requirements
            ],
        }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def capability_root() -> Path:
    return repo_root() / "capability"


def discover_instances(root: Path | None = None) -> dict[str, list[Path]]:
    """Map instance id to the modules that make up that instance."""
    root = root or capability_root()
    found: dict[str, list[Path]] = {}

    provider = root / "model" / "model_provider"
    if provider.is_dir():
        for child in sorted(path for path in provider.iterdir() if path.is_dir()):
            plugins = sorted(child.glob("*_plugin.py"))
            if plugins:
                found[f"model.{child.name}"] = plugins

    compression = root / "context" / "context_compression"
    if compression.is_dir():
        for child in sorted(path for path in compression.iterdir() if path.is_dir()):
            modules = sorted(
                path
                for path in child.glob("*.py")
                if path.name != "__init__.py" and not path.name.startswith("test_")
            )
            if modules:
                found[f"context.{child.name}"] = modules

    prompt_root = root / "prompt"
    if prompt_root.is_dir():
        for main in sorted(prompt_root.rglob("prompt_main.py")):
            relative = main.relative_to(prompt_root)
            group = relative.parts[0] if len(relative.parts) > 1 else main.parent.name
            found[f"prompt.{group.replace(' ', '_')}"] = [main]

    tools = root / "tools"
    if tools.is_dir():
        for plugin in sorted(tools.rglob("*_plugin.py")):
            stem = plugin.name[: -len("_plugin.py")]
            ident = f"tools.{stem}"
            if ident in found:
                ident = f"tools.{plugin.parent.name}.{stem}"
            found[ident] = [plugin]

    sandbox = root / "sandbox" / "sandbox" / "src" / "sandbox_plugin.py"
    if sandbox.is_file() and _defines_load(sandbox):
        found["sandbox.sandbox"] = [sandbox]

    return {key: paths for key, paths in found.items() if _paths_define_load(paths)}


def _defines_load(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return "def load(" in text


def _paths_define_load(paths: list[Path]) -> bool:
    return any(_defines_load(path) for path in paths)


def adapter_module_path() -> Path:
    """The one process forwarder. Discovery does not treat it as a capability."""
    return capability_root() / "process_adapter.py"


def describe_instance(
    instance_id: str,
    catalog: dict[str, list[Path]] | None = None,
) -> CapabilityDefinition:
    """Return a process-safe definition for exactly one capability instance."""
    catalog = discover_instances() if catalog is None else catalog
    resolved = resolve_instance_id(instance_id, catalog)
    return CapabilityDefinition(
        instance_id=resolved,
        module_paths=_with_adapter(tuple(str(path) for path in catalog[resolved])),
        entrypoint="load",
    )


def _with_adapter(module_paths: tuple[str, ...]) -> tuple[str, ...]:
    """Record the forwarder path. The process still calls create_adapter()."""
    adapter = adapter_module_path()
    if not adapter.is_file():
        return module_paths
    resolved = {Path(path).resolve() for path in module_paths}
    if adapter.resolve() in resolved:
        return module_paths
    return module_paths + (str(adapter),)


def resolve_instance_id(instance_id: str, catalog: dict[str, list[Path]] | None = None) -> str:
    """Return the registry id for an instance, including replica names like tools.bash-0."""
    catalog = discover_instances() if catalog is None else catalog
    if instance_id in catalog:
        return instance_id
    base, separator, suffix = instance_id.rpartition("-")
    if separator and suffix.isdigit() and base in catalog:
        return base
    known = ", ".join(sorted(catalog))
    raise KeyError(f"Unknown capability instance {instance_id!r}. Known: {known}")


def load_capability(
    instance_id: str,
) -> tuple[list[ModuleType], CapabilityDefinition]:
    """Import one capability from a single catalog scan."""
    catalog = discover_instances()
    definition = describe_instance(instance_id, catalog)
    loaded: list[ModuleType] = []
    for path in definition.module_paths:
        module_name = (
            "capability_instance."
            + definition.instance_id.replace(".", "_")
            + "."
            + Path(path).stem
        )
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        loaded.append(module)
    return loaded, definition


def load_instance(instance_id: str) -> list[ModuleType]:
    """Import the modules for one capability instance."""
    modules, _definition = load_capability(instance_id)
    return modules
