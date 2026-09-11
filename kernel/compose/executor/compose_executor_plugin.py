# -*- coding: utf-8 -*-
"""Execute portable Compose definitions with retries, timeouts, and resources."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from typing import Any
from uuid import uuid4

from kernel.compose.capability.capability import Capability


PLUGIN_NAME = "kernel_compose_executor"
PLUGIN_VERSION = "1.0"

COMPOSE_DEFINITION_ATTRIBUTE = "__compose_definition__"


class ComposeExecutionError(RuntimeError):
    """Compose infrastructure failure retaining its originating exception."""

    def __init__(self, message: str, *, cause: BaseException | None = None):
        super().__init__(message)
        self.cause = cause


def _compose_definition(
    compose: Mapping[str, Any] | Callable[..., Any],
) -> dict[str, Any]:
    if isinstance(compose, Mapping):
        definition = dict(compose)
    elif callable(compose):
        attached = getattr(compose, COMPOSE_DEFINITION_ATTRIBUTE, None)
        definition = (
            dict(attached)
            if isinstance(attached, Mapping)
            else {
                "name": getattr(compose, "__name__", compose.__class__.__name__),
                "version": "1",
                "interfaces": {
                    getattr(compose, "__name__", compose.__class__.__name__): {}
                },
                "handlers": {
                    getattr(compose, "__name__", compose.__class__.__name__): compose
                },
                "retry": None,
                "timeout": None,
                "requires": [],
                "kind": "compose",
            }
        )
    else:
        error = TypeError("compose must be a definition mapping or callable")
        raise ComposeExecutionError(str(error), cause=error) from error

    interfaces = definition.get("interfaces")
    handlers = definition.get("handlers")
    if not isinstance(interfaces, Mapping) or not interfaces:
        error = TypeError("compose definition is missing interfaces")
        raise ComposeExecutionError(str(error), cause=error) from error
    if not isinstance(handlers, Mapping) or not handlers:
        error = TypeError("compose definition is missing handlers")
        raise ComposeExecutionError(str(error), cause=error) from error
    if set(interfaces) != set(handlers):
        error = ValueError("compose interfaces and handlers must have matching names")
        raise ComposeExecutionError(str(error), cause=error) from error
    if any(not isinstance(contract, Mapping) for contract in interfaces.values()):
        error = TypeError("compose interface contracts must be mappings")
        raise ComposeExecutionError(str(error), cause=error) from error
    if any(not callable(handler) for handler in handlers.values()):
        error = TypeError("compose definition contains a non-callable handler")
        raise ComposeExecutionError(str(error), cause=error) from error
    definition["interfaces"] = {
        name: dict(contract) for name, contract in interfaces.items()
    }
    definition["handlers"] = dict(handlers)
    return definition


def _select_handler(
    definition: Mapping[str, Any],
    interface_name: str | None,
) -> Callable[..., Any]:
    handlers = definition["handlers"]
    selected = interface_name
    if selected is None:
        if "run" in handlers:
            selected = "run"
        elif len(handlers) == 1:
            selected = next(iter(handlers))
        else:
            error = ValueError(
                "interface is required when a compose exposes multiple interfaces"
            )
            raise ComposeExecutionError(str(error), cause=error) from error
    handler = handlers.get(selected)
    if not callable(handler):
        error = KeyError(selected)
        raise ComposeExecutionError(
            f"compose interface {selected!r} is not defined", cause=error
        ) from error
    return handler


def _retry_policy(value: Any) -> tuple[int, float, float]:
    if value is None:
        return 1, 0.0, 1.0
    if not isinstance(value, Mapping):
        raise TypeError("retry must be a mapping or None")

    attempts = value.get("max_attempts", 1)
    interval = value.get("interval_seconds", 0)
    backoff = value.get("backoff_rate", 1)
    if isinstance(attempts, bool) or not isinstance(attempts, int):
        raise TypeError("retry max_attempts must be an int")
    if attempts < 1:
        raise ValueError("retry max_attempts must be at least one")
    if isinstance(interval, bool) or not isinstance(interval, (int, float)):
        raise TypeError("retry interval_seconds must be an int or float")
    if interval < 0:
        raise ValueError("retry interval_seconds must be non-negative")
    if isinstance(backoff, bool) or not isinstance(backoff, (int, float)):
        raise TypeError("retry backoff_rate must be an int or float")
    if backoff < 0:
        raise ValueError("retry backoff_rate must be non-negative")
    return attempts, float(interval), float(backoff)


def _requirement(value: Any) -> tuple[str, int | float]:
    if isinstance(value, str):
        name, amount = value, 1
    elif isinstance(value, Mapping):
        name = value.get("resource_name", value.get("name"))
        amount = value.get("amount", 1)
    else:
        raise TypeError("resource requirements must be names or mappings")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("resource requirement is missing a name")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise TypeError("resource requirement amount must be an int or float")
    if amount <= 0:
        raise ValueError("resource requirement amount must be greater than zero")
    return name.strip(), amount


def _context_value(context: Any, name: str) -> Any:
    if context is None:
        return None
    if isinstance(context, Mapping):
        return context.get(name)
    return getattr(context, name, None)


def _owner_id(context: Any) -> str:
    identity = [
        _context_value(context, "process_id"),
        _context_value(context, "run_id"),
        _context_value(context, "current_command_index"),
    ]
    present = [str(value) for value in identity if value is not None]
    return ":".join(present) if present else uuid4().hex


def _arguments(
    function: Callable[..., Any], context: Any, input_value: Any
) -> tuple[Any, ...]:
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return (input_value,)

    positional = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    ]
    if (
        len(positional) >= 2
        and positional[0].name.lower() in {"context", "res"}
    ):
        try:
            signature.bind(context, input_value)
            return context, input_value
        except TypeError:
            pass

    candidates = ((input_value,), (context, input_value), ())
    for arguments in candidates:
        try:
            signature.bind(*arguments)
            return arguments
        except TypeError:
            continue
    error = TypeError(
        "compose function must accept input, context and input, or no arguments"
    )
    raise ComposeExecutionError(str(error), cause=error) from error


async def _await_if_needed(value: Any, timeout: Any) -> Any:
    if not inspect.isawaitable(value):
        return value
    if timeout is None:
        return await value
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        error = TypeError("compose timeout must be an int, float, or None")
        if inspect.iscoroutine(value):
            value.close()
        raise ComposeExecutionError(str(error), cause=error) from error
    if timeout <= 0:
        error = ValueError("compose timeout must be greater than zero")
        if inspect.iscoroutine(value):
            value.close()
        raise ComposeExecutionError(str(error), cause=error) from error
    return await asyncio.wait_for(value, timeout=float(timeout))


async def _call_maybe_async(function: Callable[..., Any], *args: Any) -> Any:
    return await _await_if_needed(function(*args), None)


async def _invoke(
    function: Callable[..., Any],
    arguments: tuple[Any, ...],
    timeout: Any,
) -> Any:
    if inspect.iscoroutinefunction(function):
        return await _await_if_needed(function(*arguments), timeout)
    result = await asyncio.to_thread(function, *arguments)
    return await _await_if_needed(result, timeout)


class ComposeExecutor:
    """Execute Composes using an optionally injected ResourcePool."""

    def __init__(self, resources: Any = None):
        self.resources = resources

    async def execute(
        self,
        compose: Mapping[str, Any] | Callable[..., Any],
        input: Any = None,
        context: Any = None,
        resources: Any = None,
        interface: str | None = None,
    ) -> Any:
        definition = _compose_definition(compose)
        selected_handler = _select_handler(definition, interface)
        timeout = definition.get("timeout")
        requirements = definition.get("requires") or ()
        pool = resources if resources is not None else self.resources

        try:
            attempts, interval, backoff = _retry_policy(definition.get("retry"))
            normalized_requirements = [
                _requirement(value) for value in requirements
            ]
        except ComposeExecutionError:
            raise
        except (TypeError, ValueError) as error:
            raise ComposeExecutionError(str(error), cause=error) from error

        if normalized_requirements and pool is None:
            error = RuntimeError(
                "compose requires resources but no resource pool is configured"
            )
            raise ComposeExecutionError(str(error), cause=error) from error
        if pool is not None:
            if not callable(getattr(pool, "acquire", None)):
                error = TypeError("resource pool must provide acquire")
                raise ComposeExecutionError(str(error), cause=error) from error
            if not callable(getattr(pool, "release", None)):
                error = TypeError("resource pool must provide release")
                raise ComposeExecutionError(str(error), cause=error) from error

        leases: list[Any] = []
        owner = _owner_id(context)
        try:
            for name, amount in normalized_requirements:
                lease = await _call_maybe_async(
                    pool.acquire, name, owner, amount
                )
                leases.append(lease)
        except BaseException:
            for lease in reversed(leases):
                try:
                    await _call_maybe_async(pool.release, lease)
                except BaseException:
                    pass
            raise

        execution_error: BaseException | None = None
        try:
            arguments = _arguments(selected_handler, context, input)
            delay = interval
            for attempt in range(1, attempts + 1):
                try:
                    return await _invoke(selected_handler, arguments, timeout)
                except Exception:
                    if attempt >= attempts:
                        raise
                    if delay > 0:
                        await asyncio.sleep(delay)
                    delay *= backoff
            raise AssertionError("unreachable retry state")
        except BaseException as error:
            execution_error = error
            raise
        finally:
            release_error: BaseException | None = None
            for lease in reversed(leases):
                try:
                    await _call_maybe_async(pool.release, lease)
                except BaseException as error:
                    if release_error is None:
                        release_error = error
            if release_error is not None and execution_error is None:
                raise ComposeExecutionError(
                    "failed to release compose resources",
                    cause=release_error,
                ) from release_error


class ComposeExecutorCapability(Capability):
    name = "kernel_compose_executor"
    version = "1.0"
    kind = "compose.executor"
    provides = ("compose.executor",)

