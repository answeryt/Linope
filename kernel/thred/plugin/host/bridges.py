"""Compatibility bridges from existing leaf ABIs to domain services."""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterable, Mapping
from typing import Any

from .contracts import PluginDescriptor


def bridge_plugin(module: Any, descriptor: PluginDescriptor) -> Any:
    """Return one installer for the descriptor's explicitly declared kind."""

    kind = descriptor.artifact.kind
    if kind in {"recipe", "entry_point"}:
        entry = descriptor.artifact.entry
        return getattr(module, entry) if entry and hasattr(module, entry) else module
    if kind in {"module", "capability"}:
        return _module_bridge(module, descriptor)
    if kind == "tool":
        return _tool_bridge(module)
    if kind in {"model", "model_adapter"}:
        return _model_bridge(module, descriptor)
    if kind in {"pipeline", "transform"}:
        return _pipeline_bridge(module, descriptor)
    if kind in {"prompt", "compression", "sandbox", "mcp", "ui"}:
        return _contribution_bridge(module, descriptor, kind)
    raise ValueError(f"unsupported plugin kind: {kind!r}")


def _module_bridge(module: Any, descriptor: PluginDescriptor) -> Any:
    def apply(ctx: Any, _config: Any) -> None:
        key = str(descriptor.metadata.get("capability", descriptor.artifact.name))
        ctx.provide(key, module)

    return apply


def _tool_bridge(module: Any) -> Any:
    schemas = getattr(module, "tool_schemas", None)
    dispatch = getattr(module, "dispatch", None)
    if not callable(schemas) or not callable(dispatch):
        raise TypeError("tool plugin must provide tool_schemas() and dispatch()")

    def apply(ctx: Any, _config: Any) -> None:
        ctx.get("tools").register(schemas(), dispatch)

    return apply


def _model_bridge(module: Any, descriptor: PluginDescriptor) -> Any:
    entry = descriptor.artifact.entry or "call_api"
    call = getattr(module, entry, None)
    if not callable(call):
        raise TypeError(f"model plugin must provide callable {entry!r}")
    provider = descriptor.metadata.get("provider", descriptor.artifact.name)
    if not isinstance(provider, str) or not provider:
        raise ValueError("model descriptor provider must be a non-empty string")

    def apply(ctx: Any, config: Any) -> None:
        defaults = config if isinstance(config, Mapping) else {}
        adapter = FunctionModelAdapter(call, defaults)
        ctx.get("llm").register_adapter([provider], adapter)

    return apply


def _pipeline_bridge(module: Any, descriptor: PluginDescriptor) -> Any:
    entry = descriptor.artifact.entry
    if not entry:
        raise ValueError("pipeline descriptors require an entry function")
    transform = getattr(module, entry, None)
    if not callable(transform):
        raise TypeError(f"pipeline plugin must provide callable {entry!r}")
    metadata = descriptor.metadata

    def apply(ctx: Any, _config: Any) -> None:
        ctx.get("pipelines").register(
            descriptor.artifact.name,
            transform,
            requires=_strings(metadata.get("requires_capabilities", ())),
            provides=_strings(metadata.get("provides", ())),
            before=_strings(metadata.get("before", ())),
            after=_strings(metadata.get("after", ())),
            priority=int(metadata.get("priority", 0)),
        )

    return apply


def _contribution_bridge(
    module: Any,
    descriptor: PluginDescriptor,
    service: str,
) -> Any:
    entry = descriptor.artifact.entry
    value = getattr(module, entry) if entry else module

    def apply(ctx: Any, _config: Any) -> None:
        ctx.get(service).register(
            descriptor.artifact.name,
            value,
            **dict(descriptor.metadata),
        )

    return apply


class FunctionModelAdapter:
    """Bridge an existing ``call_api(**kwargs)`` leaf to streaming requests."""

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
            else {
                name: values[name]
                for name in self.signature.parameters
                if name in values
            }
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


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)
