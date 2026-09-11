"""Resolve capability requirements into an injectable, callable composition plan."""

from __future__ import annotations

import inspect
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from kernel.compose.capability.discovery.contracts import (
    Artifact,
    Cardinality,
    PluginDescriptor,
    Requirement,
    cluster_of,
    in_cluster,
    parse_requirements,
)
from kernel.compose.capability.capability import Capability, inject


class ComposeResolutionError(RuntimeError):
    """A compose specification cannot be resolved from the available capabilities."""


@dataclass(frozen=True, slots=True)
class ComposeSpec:
    """Requirements and constraints for a composition before any capability is loaded."""

    name: str
    requires: tuple[Requirement, ...]
    constraints: Mapping[str, Any] = field(default_factory=dict)
    entry: str | None = None
    kind: str = "compose"
    version: str = "1"

    def __init__(
        self,
        name: str,
        requires: Iterable[Any],
        *,
        constraints: Mapping[str, Any] | None = None,
        entry: str | None = None,
        kind: str = "compose",
        version: str = "1",
    ) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("compose spec name must not be a non-empty string")
        if not isinstance(kind, str) or not kind:
            raise ValueError("compose spec kind must be a non-empty string")
        if not isinstance(version, str) or not version:
            raise ValueError("compose spec version must be a non-empty string")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "requires", tuple(parse_requirements(requires)))
        object.__setattr__(self, "constraints", dict(constraints or {}))
        object.__setattr__(self, "entry", entry)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "version", version)


@dataclass(frozen=True, slots=True)
class DiscoveredCapability:
    """A plugin class or descriptor used before values are provided."""

    descriptor: PluginDescriptor
    provides: tuple[str, ...]
    requires: tuple[Requirement, ...]
    constraints: Mapping[str, Any]
    priority: int = 0
    plugin_cls: type[Capability] | None = None

    @property
    def identity(self) -> str:
        artifact = self.descriptor.artifact
        return f"{artifact.name}:{artifact.version}"

    @property
    def name(self) -> str:
        return self.descriptor.artifact.name

    @classmethod
    def from_descriptor(cls, descriptor: PluginDescriptor) -> "DiscoveredCapability":
        metadata = descriptor.metadata
        provides = _strings(
            metadata.get(
                "provides",
                metadata.get("capability", descriptor.artifact.name),
            )
        )
        constraints = metadata.get("constraints", {})
        if constraints is None:
            constraints = {}
        if not isinstance(constraints, Mapping):
            raise TypeError("capability descriptor constraints must be a mapping")
        return cls(
            descriptor=descriptor,
            provides=provides,
            requires=descriptor.requirements,
            constraints=dict(constraints),
            priority=int(metadata.get("priority", 0)),
        )

    @classmethod
    def from_plugin(cls, plugin_cls: type[Capability]) -> "DiscoveredCapability":
        artifact = Artifact(
            name=plugin_cls.name,
            version=plugin_cls.version,
            kind=plugin_cls.kind,
        )
        requirements = tuple(parse_requirements(plugin_cls.requires))
        provides = _strings(plugin_cls.provides or plugin_cls.name)
        descriptor = PluginDescriptor(
            artifact=artifact,
            requirements=requirements,
            config=plugin_cls.config,
            metadata={
                "provides": provides,
                "constraints": dict(plugin_cls.constraints),
                "priority": plugin_cls.priority,
            },
        )
        return cls(
            descriptor=descriptor,
            provides=provides,
            requires=requirements,
            constraints=dict(plugin_cls.constraints),
            priority=int(plugin_cls.priority),
            plugin_cls=plugin_cls,
        )

    def instantiate(self) -> Capability:
        if self.plugin_cls is None:
            raise ComposeResolutionError(f"capability {self.name!r} has no plugin class to inject")
        return self.plugin_cls()

    @property
    def cluster(self) -> str:
        return cluster_of(self.descriptor.artifact.kind)

    def satisfies(self, requirement: Requirement | str) -> bool:
        key = requirement.capability if isinstance(requirement, Requirement) else requirement
        kind = self.descriptor.artifact.kind
        candidates = (self.name, kind, *self.provides)
        return any(item == key or in_cluster(item, key) for item in candidates if item)


class CapabilityCatalog:
    """Inventory of available capabilities. It does not choose between them."""

    def __init__(self, capabilities: Iterable[DiscoveredCapability]) -> None:
        self._capabilities = tuple(capabilities)

    @classmethod
    def from_descriptors(
        cls,
        descriptors: Iterable[PluginDescriptor],
    ) -> "CapabilityCatalog":
        return cls(DiscoveredCapability.from_descriptor(item) for item in descriptors)

    @classmethod
    def from_plugins(
        cls,
        types: Iterable[type[Capability]],
    ) -> "CapabilityCatalog":
        return cls(DiscoveredCapability.from_plugin(item) for item in types)

    @classmethod
    def discover(cls, source: Any) -> "CapabilityCatalog":
        registered = getattr(source, "registered", None)
        if callable(registered):
            return cls.from_plugins(registered())
        discover = getattr(source, "discover", None)
        if callable(discover):
            return cls.from_descriptors(discover())
        raise TypeError("capability source must provide registered() or discover()")

    def list(self, namespace: str | None = None) -> tuple[DiscoveredCapability, ...]:
        if namespace is None:
            return self._capabilities
        return tuple(
            capability
            for capability in self._capabilities
            if capability.satisfies(namespace)
        )

    def find(self, requirement: Requirement | str) -> tuple[DiscoveredCapability, ...]:
        return tuple(
            capability
            for capability in self._capabilities
            if capability.satisfies(requirement)
        )


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    """Matcher output. Rejections are data, not exceptions."""

    accepted: bool
    score: int = 0
    reason: str = ""


class CapabilityMatcher:
    """Check whether a capability can satisfy one requirement under constraints."""

    def compatible(
        self,
        requirement: Requirement | str,
        capability: DiscoveredCapability,
        constraints: Mapping[str, Any] | None = None,
    ) -> CompatibilityResult:
        if not capability.satisfies(requirement):
            key = requirement.capability if isinstance(requirement, Requirement) else requirement
            return CompatibilityResult(False, reason=f"does not provide {key!r}")
        ok, reason = _constraints_match(constraints or {}, capability)
        if not ok:
            return CompatibilityResult(False, reason=reason)
        return CompatibilityResult(True, score=capability.priority)


@dataclass(frozen=True, slots=True)
class CapabilityGraph:
    """Resolved capability nodes and dependency edges."""

    nodes: tuple[DiscoveredCapability, ...]
    edges: Mapping[str, tuple[str, ...]]

    def order(self) -> tuple[DiscoveredCapability, ...]:
        by_id = {node.identity: node for node in self.nodes}
        pending = set(by_id)
        ordered: list[DiscoveredCapability] = []
        while pending:
            ready = sorted(
                (
                    identity
                    for identity in pending
                    if not (set(self.edges.get(identity, ())) & pending)
                ),
                key=lambda identity: list(by_id).index(identity),
            )
            if not ready:
                raise ComposeResolutionError(f"capability dependency cycle: {sorted(pending)!r}")
            for identity in ready:
                ordered.append(by_id[identity])
                pending.remove(identity)
        return tuple(ordered)


class CapabilityGraphResolver:
    """Resolve a ComposeSpec into a graph before providing capability values."""

    def __init__(
        self,
        catalog: CapabilityCatalog,
        *,
        matcher: CapabilityMatcher | None = None,
    ) -> None:
        self.catalog = catalog
        self.matcher = matcher or CapabilityMatcher()

    def resolve(self, spec: ComposeSpec) -> CapabilityGraph:
        selected: dict[str, DiscoveredCapability] = {}
        queue: deque[Requirement] = deque(spec.requires)

        while queue:
            requirement = queue.popleft()
            if _satisfied(requirement, selected.values()):
                continue
            if requirement.cardinality is Cardinality.MANY:
                matches = self._select_all(requirement, spec.constraints)
                if not matches:
                    if requirement.optional:
                        continue
                    raise ComposeResolutionError(
                        f"cannot resolve capability {requirement.capability!r}: no candidates"
                    )
                for capability in matches:
                    if capability.identity in selected:
                        continue
                    selected[capability.identity] = capability
                    queue.extend(capability.requires)
                continue
            capability = self._select(requirement, spec.constraints)
            selected[capability.identity] = capability
            queue.extend(capability.requires)

        return CapabilityGraph(
            nodes=tuple(selected.values()),
            edges=_dependency_edges(tuple(selected.values())),
        )

    def plan(self, spec: ComposeSpec) -> "CompositionPlan":
        return CompositionPlan(spec=spec, graph=self.resolve(spec))

    def _select(
        self,
        requirement: Requirement,
        constraints: Mapping[str, Any],
    ) -> DiscoveredCapability:
        matches: list[tuple[int, str, DiscoveredCapability]] = []
        rejected: list[str] = []
        for capability in self.catalog.find(requirement):
            result = self.matcher.compatible(requirement, capability, constraints)
            if result.accepted:
                matches.append((result.score, capability.identity, capability))
            else:
                rejected.append(f"{capability.identity}: {result.reason}")
        if not matches:
            detail = "; ".join(rejected) if rejected else "no candidates"
            raise ComposeResolutionError(
                f"cannot resolve capability {requirement.capability!r}: {detail}"
            )
        matches.sort(key=lambda item: (-item[0], item[1]))
        return matches[0][2]

    def _select_all(
        self,
        requirement: Requirement,
        constraints: Mapping[str, Any],
    ) -> tuple[DiscoveredCapability, ...]:
        matches: list[DiscoveredCapability] = []
        for capability in self.catalog.find(requirement):
            result = self.matcher.compatible(requirement, capability, constraints)
            if result.accepted:
                matches.append(capability)
        matches.sort(key=lambda item: (-item.priority, item.identity))
        return tuple(matches)


@dataclass(frozen=True, slots=True)
class CompositionPlan:
    """Executable plan that injects resolved nodes and returns a callable composition."""

    spec: ComposeSpec
    graph: CapabilityGraph

    def execute(self, res: Any) -> "Composition":
        composition = Composition(self.spec, self.graph, res, None)
        for node in self.graph.order():
            composition.inject(node.instantiate())
        target = None
        if self.spec.entry:
            try:
                target = res.get(self.spec.entry)
            except LookupError:
                target = None
        return Composition(self.spec, self.graph, res, target)


class Composition:
    """Callable wrapper returned after resolved capabilities are injected."""

    def __init__(
        self,
        spec: ComposeSpec | None,
        graph: CapabilityGraph | None,
        res: Any,
        target: Any,
    ) -> None:
        self.spec = spec
        self.graph = graph
        self.res = res
        self.target = target

    @property
    def cap_bus(self) -> Any:
        return self.res.cap_bus

    def inject(self, capability: Capability) -> "Composition":
        inject(capability, self)
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        if callable(self.target):
            return self.target(*args, **kwargs)
        run = getattr(self.target, "run", None)
        if callable(run):
            return run(*args, **kwargs)
        raise TypeError("composition target is not callable")

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        result = self(*args, **kwargs)
        return await result if inspect.isawaitable(result) else result

    def unload(self) -> None:
        if self.graph is None:
            self.res.unload()
            return
        for node in reversed(self.graph.nodes):
            self.res.unload(node.identity)


def _satisfied(
    requirement: Requirement,
    capabilities: Iterable[DiscoveredCapability],
) -> bool:
    return any(capability.satisfies(requirement) for capability in capabilities)


def _dependency_edges(
    nodes: Sequence[DiscoveredCapability],
) -> dict[str, tuple[str, ...]]:
    edges: dict[str, tuple[str, ...]] = {}
    for node in nodes:
        dependencies = [
            candidate.identity
            for requirement in node.requires
            for candidate in nodes
            if candidate is not node and candidate.satisfies(requirement)
        ]
        edges[node.identity] = tuple(dict.fromkeys(dependencies))
    return edges


def _constraints_match(
    constraints: Mapping[str, Any],
    capability: DiscoveredCapability,
) -> tuple[bool, str]:
    declared = {**dict(capability.descriptor.metadata), **dict(capability.constraints)}
    for key, expected in constraints.items():
        if key == "domain" and _domain_matches(capability, expected):
            continue
        if key not in declared:
            continue
        actual = declared[key]
        if not _constraint_value_matches(actual, expected):
            return False, f"constraint {key!r} expected {expected!r}, got {actual!r}"
    return True, ""


def _domain_matches(capability: DiscoveredCapability, expected: Any) -> bool:
    domain = expected.get("equals") if isinstance(expected, Mapping) else expected
    if not isinstance(domain, str) or not domain:
        return False
    kind = capability.descriptor.artifact.kind
    if kind == domain or in_cluster(kind, domain):
        return True
    if capability.name == domain or in_cluster(capability.name, domain):
        return True
    return any(item == domain or in_cluster(item, domain) for item in capability.provides)


def _constraint_value_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, Mapping):
        if "equals" in expected and not _constraint_value_matches(actual, expected["equals"]):
            return False
        if "one_of" in expected and not _one_of(actual, expected["one_of"]):
            return False
        if "min" in expected and _numeric_cap(actual, "max") < float(expected["min"]):
            return False
        if "max" in expected and _numeric_cap(actual, "min") > float(expected["max"]):
            return False
        return True
    if isinstance(actual, (list, tuple, set, frozenset)):
        return expected in actual
    return actual == expected


def _one_of(actual: Any, expected: Any) -> bool:
    options = expected if isinstance(expected, Iterable) and not isinstance(expected, (str, bytes)) else (expected,)
    if isinstance(actual, (list, tuple, set, frozenset)):
        return bool(set(actual) & set(options))
    return actual in set(options)


def _numeric_cap(value: Any, bound: str) -> float:
    if isinstance(value, Mapping):
        raw = value.get(bound, value.get("value"))
    else:
        raw = value
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return float("-inf") if bound == "max" else float("inf")
    return float(raw)


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)
