"""Assemble a callable Model Composition from imported capability classes."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterable, Mapping
from pathlib import Path
from typing import Any, Final

from kernel.compose.capability import Capability
from kernel.compose.capability import CapabilityCatalog
from kernel.compose.capability import CapabilityContext
from kernel.compose.capability import CapabilityGraphResolver
from kernel.compose.capability import Composition
from kernel.compose.capability import ComposeSpec
from kernel.compose.capability import inject
from kernel.compose.capability import inject_capabilities

PLUGIN_NAME: Final[str] = "model_composition_runtime"
PLUGIN_VERSION: Final[str] = "1.0"
ROOT: Final[Path] = Path(__file__).resolve().parents[3]


class FunctionModelAdapter:
    """Adapt ``call_api(**kwargs)`` style providers into CapBus streams."""

    def __init__(self, call: Any, defaults: Mapping[str, Any]) -> None:
        self.call = call
        self.defaults = dict(defaults)
        self.signature = inspect.signature(call)

    async def stream(self, request: Mapping[str, Any]) -> AsyncIterable[Any]:
        values = {**self.defaults, **dict(request)}
        accepts_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in self.signature.parameters.values()
        )
        arguments = (
            values
            if accepts_kwargs
            else {name: values[name] for name in self.signature.parameters if name in values}
        )
        missing = [
            name
            for name, parameter in self.signature.parameters.items()
            if parameter.default is inspect.Parameter.empty
            and parameter.kind
            not in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }
            and name not in arguments
        ]
        if missing:
            raise TypeError(f"model request is missing arguments: {missing!r}")
        result = self.call(**arguments)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, AsyncIterable):
            async for item in result:
                yield item
        else:
            yield result


class ModelCardCapability(Capability):
    """Model card that answers CapBus.publish(route, payload=request)."""

    def activate(self, context: Any) -> None:
        self._adapter = bind_card(context, self.config)

    def on_request(self, context: Any, broadcast: Any) -> Any:
        payload = dict(getattr(broadcast, "payload", None) or ())
        if payload:
            adapter = getattr(self, "_adapter", None)
            if adapter is None:
                adapter = bind_card(context, self.config)
                self._adapter = adapter
            return {
                "handled": True,
                "stop": True,
                "owners": (self.identity,),
                "value": adapter.stream(payload),
            }
        return super().on_request(context, broadcast)


class ModelComposition:
    """A thread whose work is to execute model requests."""

    def __init__(self, res: Any) -> None:
        self.res = res

    def providers(self) -> tuple[str, ...]:
        names: list[str] = []
        for card in self.res.get_all("model.card"):
            if isinstance(card, Mapping):
                names.extend(str(item) for item in card.get("routes") or ())
        return tuple(dict.fromkeys(names))

    def stream(
        self,
        request: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> AsyncIterable[Any]:
        del context
        return self._stream(dict(request))

    async def _stream(self, request: Mapping[str, Any]) -> AsyncIterable[Any]:
        provider = request.get("provider")
        if not isinstance(provider, str) or not provider:
            raise LookupError("model request is missing provider")
        result = await self.res.cap_bus.publish(provider, payload=request)
        if isinstance(result, AsyncIterable):
            async for item in result:
                yield item
            return
        yield result

    async def run(
        self,
        request: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> Any:
        chunks = [chunk async for chunk in self.stream(request, context)]
        return chunks[0] if len(chunks) == 1 else chunks

    def __call__(
        self,
        request: Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> AsyncIterable[Any]:
        return self.stream(request, context)


class ModelCompositionRuntime(Capability):
    name = "model_composition_runtime"
    version = "1.0"
    kind = "model.thread"
    provides = ("model.thread",)
    requires = (
        "compose.runtime",
        {"capability": "model.interface", "cardinality": "many"},
        {"capability": "model.card", "cardinality": "many"},
    )
    constraints = {"domain": "model"}

    def activate(self, context: Any) -> None:
        context.provide("model.thread", ModelComposition(context), contract="ModelComposition")


def assemble(*, repo: str | Path | None = None) -> Composition:
    import capability.model as _model_plugins

    del _model_plugins
    root = Path(repo) if repo is not None else ROOT
    res = inject_capabilities(repo=root)
    try:
        return CapabilityGraphResolver(model_catalog(root)).plan(model_composition_spec()).execute(res)
    except BaseException:
        res.unload()
        raise


def model_composition_spec() -> ComposeSpec:
    return ComposeSpec(
        "model-composition",
        ["model.thread"],
        constraints={"domain": "model"},
        entry="model.thread",
    )


def model_catalog(repo: str | Path | None = None) -> CapabilityCatalog:
    import capability.model as _model_plugins
    from kernel.compose.capability.discovery.loader import kernel_capability_types

    del _model_plugins
    del repo
    kernel_capability_types()
    return CapabilityCatalog.from_plugins(Capability.registered())


def apply(res: CapabilityContext, config: Any) -> None:
    del config
    res.provide("model.thread", ModelComposition(res), contract="ModelComposition")


def bind_card(res: CapabilityContext, config: Any) -> FunctionModelAdapter:
    card = dict(config)
    interface = res.get(f"model.interface.{card['interface']}")
    adapter = FunctionModelAdapter(interface.call_api, {})
    card_id = str(card.get("card_id") or card.get("provider") or "default")
    res.provide(
        f"model.card.{card_id}",
        card,
        contract="ModelCard",
        aliases=("model.card",),
    )
    return adapter


def register_card(res: CapabilityContext, config: Any) -> None:
    bind_card(res, config)


__all__ = [
    "FunctionModelAdapter",
    "ModelCardCapability",
    "ModelComposition",
    "ModelCompositionRuntime",
    "apply",
    "assemble",
    "inject",
    "model_catalog",
    "model_composition_spec",
    "register_card",
]
