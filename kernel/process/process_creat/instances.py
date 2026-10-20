"""Resolve one capability name to one loadable plugin."""

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
    instance_id: str
    module_paths: tuple[str, ...]
    entrypoint: str | None = "load"
    resource_requirements: tuple[ResourceDefinition, ...] = ()

    def activation(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "module_paths": self.module_paths,
            "entrypoint": self.entrypoint,
            "resource_requirements": [
                {
                    "kind": str(getattr(item.kind, "value", item.kind)),
                    "required": item.required,
                    "share_mode": item.share_mode.value,
                }
                for item in self.resource_requirements
            ],
        }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def capability_root() -> Path:
    return repo_root() / "capability"


def discover_instances(root: Path | None = None) -> dict[str, list[Path]]:
    """Return one plugin path per capability id.

    Discovery intentionally recognizes only explicit entry files. It does not
    scan a directory as a multi-plugin manifest and does not load context
    compressors or other historical capability families.
    """
    root = root or capability_root()
    found: dict[str, list[Path]] = {}

    for plugin in sorted(root.rglob("*_plugin.py")):
        if _defines_load(plugin):
            capability_id = _capability_id(root, plugin)
            found[capability_id] = [plugin]

    for main in sorted(root.rglob("prompt_main.py")):
        if _defines_load(main):
            relative = main.relative_to(root / "prompt")
            group = relative.parts[0] if len(relative.parts) > 1 else main.parent.name
            found[f"prompt.{group.replace(' ', '_')}"] = [main]

    return found


def _capability_id(root: Path, plugin: Path) -> str:
    relative = plugin.relative_to(root)
    parts = list(relative.parts)
    parts.pop()
    stem = plugin.name[: -len("_plugin.py")]
    if parts and parts[0] == "model":
        return f"model.{parts[-1]}"
    if parts and parts[0] == "tools":
        return f"tools.{stem}"
    if parts and parts[0] == "sandbox":
        return "sandbox.sandbox" if len(parts) > 1 else f"sandbox.{stem}"
    return f"{parts[0] if parts else 'capability'}.{stem}"


def _defines_load(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return "def load(" in text or "async def load(" in text


def adapter_module_path() -> Path:
    return capability_root() / "process_adapter.py"


def describe_instance(
    instance_id: str,
    catalog: dict[str, list[Path]] | None = None,
) -> CapabilityDefinition:
    catalog = discover_instances() if catalog is None else catalog
    resolved = resolve_instance_id(instance_id, catalog)
    return CapabilityDefinition(
        instance_id=resolved,
        module_paths=_with_adapter((str(catalog[resolved][0]),)),
    )


def _with_adapter(module_paths: tuple[str, ...]) -> tuple[str, ...]:
    adapter = adapter_module_path()
    if not adapter.is_file():
        return module_paths
    return module_paths + (str(adapter),)


def resolve_instance_id(
    instance_id: str,
    catalog: dict[str, list[Path]] | None = None,
) -> str:
    catalog = discover_instances() if catalog is None else catalog
    if instance_id not in catalog:
        known = ", ".join(sorted(catalog))
        raise KeyError(f"Unknown capability instance {instance_id!r}. Known: {known}")
    return instance_id


def load_capability(
    instance_id: str,
) -> tuple[list[ModuleType], CapabilityDefinition]:
    catalog = discover_instances()
    definition = describe_instance(instance_id, catalog)
    loaded: list[ModuleType] = []
    for index, raw_path in enumerate(definition.module_paths):
        path = Path(raw_path)
        module_name = f"capability_instance_{index}_{path.stem}"
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
    modules, _definition = load_capability(instance_id)
    return modules
