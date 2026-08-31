"""Pluggable discovery sources that never import discovered plugin code."""

from __future__ import annotations

import ast
import importlib.metadata
import json
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .contracts import Artifact, PluginDescriptor


class CompositionSource:
    """Read descriptors already declared in a composition mapping."""

    def __init__(self, composition: Mapping[str, Any], *, base: Path | None = None):
        self.composition = composition
        self.base = base

    def discover(self) -> Iterable[PluginDescriptor]:
        entries = self.composition.get("plugins", ())
        if not isinstance(entries, list):
            raise TypeError("composition plugins must be a list")
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise TypeError("composition plugin entries must be mappings")
            yield PluginDescriptor.from_mapping(entry, base=self.base)


class StaticSnapshotSource:
    """Read a CI-produced descriptor snapshot with no dependency on CI code."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def discover(self) -> Iterable[PluginDescriptor]:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        entries = payload.get("artifacts", payload) if isinstance(payload, dict) else payload
        if not isinstance(entries, list):
            raise ValueError("plugin snapshot must contain an artifacts list")
        for entry in entries:
            if not isinstance(entry, Mapping):
                raise ValueError("snapshot artifacts must be mappings")
            yield PluginDescriptor.from_mapping(entry, base=self.path.parent)


class FileSystemSource:
    """Discover explicit manifests below user-controlled plugin roots."""

    FILENAMES = ("plugin.toml", "plugin.json", "plugin.yaml", "plugin.yml")

    def __init__(
        self,
        roots: Sequence[str | Path],
        *,
        recursive: bool = True,
    ) -> None:
        self.roots = tuple(Path(root).resolve() for root in roots)
        self.recursive = recursive

    def discover(self) -> Iterable[PluginDescriptor]:
        seen: set[Path] = set()
        for root in self.roots:
            if not root.is_dir():
                continue
            candidates = (
                root.rglob("*") if self.recursive else root.iterdir()
            )
            for directory in (root, *(path for path in candidates if path.is_dir())):
                manifest = next(
                    (directory / name for name in self.FILENAMES if (directory / name).is_file()),
                    None,
                )
                if manifest is None or manifest in seen:
                    continue
                seen.add(manifest)
                yield PluginDescriptor.from_mapping(
                    _read_manifest(manifest),
                    base=manifest.parent,
                )


class PythonPluginSource:
    """Statically index legacy ``*_plugin.py`` leaves without importing them."""

    def __init__(
        self,
        roots: Sequence[str | Path],
        *,
        pattern: str = "*_plugin.py",
    ) -> None:
        self.roots = tuple(Path(root).resolve() for root in roots)
        self.pattern = pattern

    def discover(self) -> Iterable[PluginDescriptor]:
        identities: set[tuple[str, str]] = set()
        for root in self.roots:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob(self.pattern)):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                descriptor = _python_descriptor(path)
                if descriptor is None:
                    continue
                identity = (
                    descriptor.artifact.name,
                    descriptor.artifact.version,
                )
                if identity in identities:
                    raise ValueError(f"duplicate legacy plugin: {identity!r}")
                identities.add(identity)
                yield descriptor


class EntryPointSource:
    """Expose installed Python entry points as lazy plugin descriptors."""

    def __init__(self, group: str = "open_linux.plugins") -> None:
        if not group:
            raise ValueError("entry point group must not be empty")
        self.group = group

    def discover(self) -> Iterable[PluginDescriptor]:
        for entry_point in importlib.metadata.entry_points(group=self.group):
            yield PluginDescriptor(
                Artifact(
                    entry_point.name,
                    source=f"entrypoint:{self.group}:{entry_point.name}",
                    entry=entry_point.value,
                    kind="entry_point",
                ),
                metadata={"entry_point_group": self.group},
            )


class CompositeSource:
    """Merge independent sources while rejecting duplicate identities."""

    def __init__(self, *sources: Any) -> None:
        self.sources = sources

    def discover(self) -> Iterable[PluginDescriptor]:
        seen: set[tuple[str, str]] = set()
        for source in self.sources:
            for descriptor in source.discover():
                identity = (
                    descriptor.artifact.name,
                    descriptor.artifact.version,
                )
                if identity in seen:
                    raise ValueError(f"duplicate plugin artifact: {identity!r}")
                seen.add(identity)
                yield descriptor


def source_from_mapping(
    value: Mapping[str, Any],
    *,
    base: str | Path,
) -> Any:
    """Build one discovery source declared by deployment configuration."""

    source_type = value.get("type")
    root = Path(base)
    if source_type in {"filesystem", "manifest"}:
        roots = _paths(value.get("roots", ()), root)
        return FileSystemSource(
            roots,
            recursive=bool(value.get("recursive", True)),
        )
    if source_type in {"python", "legacy_python"}:
        return PythonPluginSource(
            _paths(value.get("roots", ()), root),
            pattern=str(value.get("pattern", "*_plugin.py")),
        )
    if source_type == "snapshot":
        path = value.get("path")
        if not isinstance(path, str) or not path:
            raise ValueError("snapshot source requires a path")
        return StaticSnapshotSource(root / path)
    if source_type == "entry_points":
        return EntryPointSource(str(value.get("group", "open_linux.plugins")))
    raise ValueError(f"unknown plugin source type: {source_type!r}")


def _read_manifest(path: Path) -> Mapping[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".toml":
        payload = tomllib.loads(text)
    elif suffix == ".json":
        payload = json.loads(text)
    else:
        try:
            import yaml
        except ImportError as error:
            raise RuntimeError("PyYAML is required for YAML plugin manifests") from error
        payload = yaml.safe_load(text)
    if not isinstance(payload, Mapping):
        raise ValueError(f"plugin manifest must be a mapping: {path}")
    plugin = payload.get("plugin", payload)
    if not isinstance(plugin, Mapping):
        raise ValueError(f"plugin manifest [plugin] must be a mapping: {path}")
    return plugin


def _python_descriptor(path: Path) -> PluginDescriptor | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    constants: dict[str, Any] = {}
    functions: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.add(node.name)
        elif (
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and (target := _assignment_name(node)) is not None
        ):
            try:
                constants[target] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
    name = constants.get("PLUGIN_NAME")
    if not isinstance(name, str) or not name:
        return None
    version = constants.get("PLUGIN_VERSION", "1")
    if "apply" in functions:
        kind = "recipe"
        entry = "apply"
    elif {"tool_schemas", "dispatch"} <= functions:
        kind = "tool"
        entry = None
    elif "call_api" in functions:
        kind = "model"
        entry = "call_api"
    else:
        kind = "capability"
        entry = None
    raw = {
        "name": name,
        "version": str(version),
        "source": str(path),
        "entry": entry,
        "kind": kind,
        "requires": constants.get("PLUGIN_INJECT", ()),
    }
    if kind == "model":
        raw["provider"] = name
    return PluginDescriptor.from_mapping(raw)


def _assignment_name(node: ast.Assign | ast.AnnAssign) -> str | None:
    if isinstance(node, ast.AnnAssign):
        return node.target.id if isinstance(node.target, ast.Name) else None
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return None
    return node.targets[0].id


def _paths(value: Any, base: Path) -> tuple[Path, ...]:
    if isinstance(value, (str, Path)):
        value = [value]
    if not isinstance(value, Sequence):
        raise TypeError("plugin source roots must be a sequence")
    return tuple(
        path if path.is_absolute() else base / path
        for item in value
        for path in (Path(item),)
    )
