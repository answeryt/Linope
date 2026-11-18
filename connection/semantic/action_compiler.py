"""Compile validated semantic actions into existing kernel CLI commands."""

from __future__ import annotations

import shlex
from collections.abc import Mapping
from typing import Any

from connection.protocol.request import ActionRequest, ProtocolError
from connection.semantic.action_types import (
    CompiledAction,
    EnvironmentDefaults,
)
from connection.semantic.environment_provider import validate_environment_reference
from connection.semantic.validators import (
    changes,
    optional_text,
    positive_integer,
    positive_number,
    required_text,
    resource_bindings,
    string_list,
)


def compile_action(
    request: ActionRequest,
    defaults: EnvironmentDefaults = EnvironmentDefaults(),
) -> CompiledAction:
    """Compile one semantic request without starting a process."""

    payload = request.payload
    if request.action == "chat.send":
        text = required_text(payload, "text")
        return CompiledAction(
            action=request.action,
            commands=(_command(("model", "run", "--", text)),),
            completion="turn",
        )
    if request.action == "process.send":
        return _compile_process_send(request.action, payload)
    if request.action == "process.create":
        return _compile_process_create(request.action, payload, defaults)
    if request.action == "environment.load":
        return _compile_environment_load(request.action, payload)
    if request.action == "model.configure":
        return _compile_model_configure(request.action, payload)
    if request.action == "command.execute":
        return _compile_raw_command(request.action, payload)
    raise ProtocolError("unsupported_action", f"Unsupported action: {request.action}")


def _compile_process_send(action: str, payload: Mapping[str, Any]) -> CompiledAction:
    """Compile a message explicitly addressed to a process."""

    pid = positive_integer(payload, "pid")
    if pid is None:
        raise ProtocolError("invalid_payload", "pid is required")
    text = required_text(payload, "text")
    addresses = string_list(payload, "addresses")
    return CompiledAction(
        action=action,
        commands=(
            _command(("load", "message", str(pid), *addresses, "--", text)),
        ),
        completion="turn",
    )


def _compile_process_create(
    action: str,
    payload: Mapping[str, Any],
    defaults: EnvironmentDefaults,
) -> CompiledAction:
    """Compile one capability process creation request."""

    capability = required_text(payload, "capability")
    count = positive_integer(payload, "count")
    max_runtime = positive_number(payload, "maxRuntimeSeconds")
    process_changes = changes(payload)
    shares = string_list(payload, "shares")
    bindings = resource_bindings(payload)
    cwd = optional_text(payload, "cwd")
    explicit_env_file = optional_text(payload, "envFile")
    env_file = explicit_env_file or defaults.path
    env_keys = string_list(payload, "envKeys") if "envKeys" in payload else defaults.keys
    if env_keys and not env_file:
        raise ProtocolError("invalid_payload", "envKeys requires envFile or a loaded environment")
    if env_file:
        env_file, env_keys = validate_environment_reference(env_file, env_keys)

    parts: list[str] = ["process", "start", capability]
    for topic, value in process_changes:
        parts.extend(("--change", f"{topic}={value}"))
    if count is not None:
        parts.extend(("--count", str(count)))
    if cwd is not None:
        parts.extend(("--cwd", cwd))
    if max_runtime is not None:
        parts.extend(("--max-runtime-seconds", _number_text(max_runtime)))
    for share in shares:
        parts.extend(("--share", share))
    for kind, identity in bindings:
        parts.extend(("--with", f"{kind}={identity}"))
    if bool_value(payload, "once"):
        parts.append("--once")
    if bool_value(payload, "ping"):
        parts.append("--ping")
    if env_file:
        parts.extend(("--env-file", env_file))
    for key in env_keys:
        parts.extend(("--env", key))

    return CompiledAction(
        action=action,
        commands=(_command(parts),),
        completion="command",
    )


def _compile_environment_load(action: str, payload: Mapping[str, Any]) -> CompiledAction:
    """Compile and remember an environment file reference."""

    path = required_text(payload, "path")
    path, keys = validate_environment_reference(path, string_list(payload, "keys"))
    return CompiledAction(
        action=action,
        commands=(_command(("load", "env", path)),),
        completion="command",
        environment_update=EnvironmentDefaults(path=path, keys=keys),
    )


def _compile_model_configure(action: str, payload: Mapping[str, Any]) -> CompiledAction:
    """Compile model core and model-card configuration commands."""

    commands: list[str] = []
    cores = positive_integer(payload, "cores")
    if cores is not None:
        commands.append(_command(("model", "cores", str(cores))))

    capability = optional_text(payload, "capability")
    model_changes = changes(payload)
    if model_changes and capability is None:
        raise ProtocolError("invalid_payload", "model changes require a capability")
    if capability is not None:
        parts = ["model", "use", capability]
        for topic, value in model_changes:
            parts.extend(("--change", f"{topic}={value}"))
        commands.append(_command(parts))

    if not commands:
        raise ProtocolError("invalid_payload", "model.configure needs cores or capability")
    return CompiledAction(action=action, commands=tuple(commands), completion="command")


def _compile_raw_command(action: str, payload: Mapping[str, Any]) -> CompiledAction:
    """Compile the deliberately narrow legacy command escape hatch."""

    command = required_text(payload, "command")
    try:
        words = tuple(shlex.split(command))
    except ValueError as exc:
        raise ProtocolError("invalid_payload", "command has invalid quoting") from exc
    if not words:
        raise ProtocolError("invalid_payload", "command must not be empty")
    completion = "session" if words[0] in {"exit", "quit"} else "command"
    if words[:2] in (("model", "run"), ("load", "message")):
        completion = "turn"
    return CompiledAction(action=action, commands=(command,), completion=completion)


def bool_value(payload: Mapping[str, Any], name: str) -> bool:
    """Read an optional strict boolean flag."""

    value = payload.get(name, False)
    if not isinstance(value, bool):
        raise ProtocolError("invalid_payload", f"{name} must be a boolean")
    return value


def _command(parts: tuple[str, ...] | list[str]) -> str:
    return shlex.join(parts)


def _number_text(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)
