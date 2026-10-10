# -*- coding: utf-8 -*-
"""Standalone MCP configuration loading and normalization plugin."""

from __future__ import annotations

import json
import math
import os
import re
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse


PLUGIN_NAME = "mcp_configuration"
PLUGIN_VERSION = "1.0"
_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


class MCPConfigError(ValueError):
    """Raised when an MCP configuration file or server entry is invalid."""


@dataclass
class MCPServerConfig:
    """Normalized transport, feature, and lifecycle configuration."""

    name: str
    enabled: bool = True
    transport: str = "stdio"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    auth: Any = None
    oauth: dict[str, Any] = field(default_factory=dict)
    ssl_verify: bool | str = True
    client_cert: Any = None
    client_key: str | None = None
    connect_timeout: float = 60.0
    read_timeout: float = 300.0
    tool_timeout: float = 60.0
    preflight_timeout: float = 5.0
    skip_preflight: bool = False
    keepalive_interval: float = 180.0
    initial_connect_retries: int = 3
    max_reconnect_retries: int = 5
    max_backoff: float = 60.0
    parked_retry_interval: float = 300.0
    jitter: float = 0.2
    shutdown_timeout: float = 10.0
    idle_timeout_seconds: float | None = None
    max_lifetime_seconds: float | None = None
    encoding: str = "utf-8"
    encoding_error_handler: str = "strict"
    supports_parallel_tool_calls: bool = False
    tools: dict[str, Any] = field(default_factory=dict)
    sampling: dict[str, Any] = field(default_factory=dict)
    elicitation: dict[str, Any] = field(default_factory=dict)
    lifecycle: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return connector-ready data without null transport keys."""
        output = asdict(self)
        output.pop("name", None)
        metadata = output.pop("metadata", {})
        output.update(metadata)
        if self.transport == "stdio":
            for key in (
                "url", "headers", "auth", "oauth", "client_cert", "client_key",
            ):
                output.pop(key, None)
        else:
            for key in ("command", "args", "env", "cwd"):
                output.pop(key, None)
        return {key: value for key, value in output.items() if value is not None}


class MCPConfigPlugin:
    """Load JSON/TOML/YAML and validate complete MCP server settings."""

    _KNOWN_KEYS = {
        "enabled", "transport", "command", "args", "env", "cwd", "url",
        "headers", "auth", "oauth", "ssl_verify", "client_cert", "client_key",
        "connect_timeout", "read_timeout", "tool_timeout",
        "timeout", "preflight_timeout", "skip_preflight", "keepalive_interval",
        "initial_connect_retries", "max_reconnect_retries", "max_backoff",
        "parked_retry_interval", "jitter", "shutdown_timeout",
        "idle_timeout_seconds", "max_lifetime_seconds", "encoding",
        "encoding_error_handler", "supports_parallel_tool_calls", "tools",
        "sampling", "elicitation", "lifecycle",
    }

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
        secret_getter: Callable[[str, Any], Any] | None = None,
        safe_mode: bool = False,
    ) -> None:
        self.env = env if env is not None else os.environ
        self.secret_getter = secret_getter
        self.safe_mode = safe_mode

    @staticmethod
    def _bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        if isinstance(value, (int, float)) and value in {0, 1}:
            return bool(value)
        raise MCPConfigError(f"Expected a boolean value, got {value!r}.")

    @staticmethod
    def _positive_float(value: Any, label: str, default: float) -> float:
        if value is None:
            return default
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise MCPConfigError(f"{label} must be numeric.") from error
        if not math.isfinite(number) or number <= 0:
            raise MCPConfigError(f"{label} must be a positive finite number.")
        return number

    @staticmethod
    def _mapping(value: Any, label: str) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise MCPConfigError(f"{label} must be a mapping.")
        return dict(value)

    @staticmethod
    def _nonnegative_int(value: Any, label: str, default: int) -> int:
        if value is None:
            return default
        try:
            number = int(value)
        except (TypeError, ValueError) as error:
            raise MCPConfigError(f"{label} must be an integer.") from error
        if number < 0:
            raise MCPConfigError(f"{label} must not be negative.")
        return number

    @staticmethod
    def _optional_seconds(value: Any, label: str) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError) as error:
            raise MCPConfigError(f"{label} must be numeric.") from error
        if not math.isfinite(number) or number < 0:
            raise MCPConfigError(f"{label} must be finite and non-negative.")
        return number or None

    def interpolate(self, value: Any) -> Any:
        """Resolve environment placeholders recursively."""
        if isinstance(value, str):
            def replace(match: re.Match[str]) -> str:
                name = match.group(1).strip()
                if name.startswith("env:"):
                    name = name[4:].strip()
                fallback = match.group(0)
                if self.secret_getter is not None:
                    resolved = self.secret_getter(name, fallback)
                else:
                    resolved = self.env.get(name, fallback)
                return fallback if resolved is None else str(resolved)

            return _ENV_PATTERN.sub(replace, value)
        if isinstance(value, Mapping):
            return {key: self.interpolate(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.interpolate(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.interpolate(item) for item in value)
        return value

    @staticmethod
    def load_document(path: str | os.PathLike[str]) -> dict[str, Any]:
        """Read one JSON, TOML, or YAML configuration document."""
        config_path = Path(path).expanduser()
        if not config_path.is_file():
            raise FileNotFoundError(f"MCP config file not found: {config_path}")
        suffix = config_path.suffix.lower()
        raw = config_path.read_bytes()
        try:
            if suffix == ".json":
                document = json.loads(raw.decode("utf-8"))
            elif suffix == ".toml":
                document = tomllib.loads(raw.decode("utf-8"))
            elif suffix in {".yaml", ".yml"}:
                try:
                    import yaml
                except ImportError as error:
                    raise MCPConfigError(
                        "PyYAML is required to read YAML MCP configuration.",
                    ) from error
                document = yaml.safe_load(raw.decode("utf-8"))
            else:
                raise MCPConfigError(
                    f"Unsupported MCP config extension: {suffix or '<none>'}",
                )
        except (UnicodeError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
            raise MCPConfigError(f"Cannot parse MCP config: {error}") from error
        if not isinstance(document, dict):
            raise MCPConfigError("MCP configuration root must be a mapping.")
        return document

    def normalize_server(
        self,
        name: str,
        value: Mapping[str, Any],
    ) -> MCPServerConfig:
        """Validate and normalize one server entry."""
        if not isinstance(name, str) or not name.strip():
            raise MCPConfigError("MCP server names must be non-empty strings.")
        if not isinstance(value, Mapping):
            raise MCPConfigError(f"MCP server {name!r} must be a mapping.")
        config = self.interpolate(dict(value))
        enabled = self._bool(config.get("enabled"), True)

        has_url = isinstance(config.get("url"), str) and bool(config["url"].strip())
        has_command = (
            isinstance(config.get("command"), str)
            and bool(config["command"].strip())
        )
        if has_url == has_command:
            raise MCPConfigError(
                f"MCP server {name!r} must specify exactly one of url or command.",
            )

        if has_url:
            parsed = urlparse(config["url"].strip())
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
                raise MCPConfigError(
                    f"MCP server {name!r} URL must be absolute HTTP(S).",
                )
            transport = str(config.get("transport", "streamable_http")).lower()
            aliases = {
                "http": "streamable_http",
                "streamable-http": "streamable_http",
                "streamable_http": "streamable_http",
                "sse": "sse",
            }
            if transport not in aliases:
                raise MCPConfigError(
                    f"MCP server {name!r} has unsupported transport {transport!r}.",
                )
            transport = aliases[transport]
        else:
            transport = "stdio"

        args = config.get("args") or []
        if not isinstance(args, list):
            raise MCPConfigError(f"MCP server {name!r} args must be a list.")
        encoding_errors = str(config.get("encoding_error_handler", "strict"))
        if encoding_errors not in {"strict", "ignore", "replace"}:
            raise MCPConfigError(
                f"MCP server {name!r} encoding_error_handler is invalid.",
            )

        lifecycle = self._mapping(config.get("lifecycle"), "lifecycle")
        try:
            jitter = float(config.get("jitter", 0.2))
        except (TypeError, ValueError) as error:
            raise MCPConfigError("jitter must be numeric.") from error
        if not math.isfinite(jitter) or not 0 <= jitter < 1:
            raise MCPConfigError("jitter must be in [0, 1).")

        metadata = {
            key: item
            for key, item in config.items()
            if key not in self._KNOWN_KEYS
        }
        return MCPServerConfig(
            name=name,
            enabled=enabled,
            transport=transport,
            command=config.get("command"),
            args=[str(item) for item in args],
            env={
                str(key): str(item)
                for key, item in self._mapping(config.get("env"), "env").items()
            },
            cwd=config.get("cwd"),
            url=config.get("url"),
            headers={
                str(key): str(item)
                for key, item in self._mapping(
                    config.get("headers"),
                    "headers",
                ).items()
            },
            auth=config.get("auth"),
            oauth=self._mapping(config.get("oauth"), "oauth"),
            ssl_verify=config.get("ssl_verify", True),
            client_cert=config.get("client_cert"),
            client_key=config.get("client_key"),
            connect_timeout=self._positive_float(
                config.get("connect_timeout"),
                "connect_timeout",
                60.0,
            ),
            read_timeout=self._positive_float(
                config.get("read_timeout"),
                "read_timeout",
                300.0,
            ),
            tool_timeout=self._positive_float(
                config.get("tool_timeout", config.get("timeout")),
                "tool_timeout",
                60.0,
            ),
            preflight_timeout=self._positive_float(
                config.get("preflight_timeout"),
                "preflight_timeout",
                5.0,
            ),
            skip_preflight=self._bool(config.get("skip_preflight"), False),
            keepalive_interval=max(
                5.0,
                self._positive_float(
                    config.get("keepalive_interval"),
                    "keepalive_interval",
                    180.0,
                ),
            ),
            initial_connect_retries=self._nonnegative_int(
                config.get("initial_connect_retries"),
                "initial_connect_retries",
                3,
            ),
            max_reconnect_retries=self._nonnegative_int(
                config.get("max_reconnect_retries"),
                "max_reconnect_retries",
                5,
            ),
            max_backoff=self._positive_float(
                config.get("max_backoff"),
                "max_backoff",
                60.0,
            ),
            parked_retry_interval=self._positive_float(
                config.get("parked_retry_interval"),
                "parked_retry_interval",
                300.0,
            ),
            jitter=jitter,
            shutdown_timeout=self._positive_float(
                config.get("shutdown_timeout"),
                "shutdown_timeout",
                10.0,
            ),
            idle_timeout_seconds=self._optional_seconds(
                config.get(
                    "idle_timeout_seconds",
                    lifecycle.get("idle_timeout_seconds"),
                ),
                "idle_timeout_seconds",
            ),
            max_lifetime_seconds=self._optional_seconds(
                config.get(
                    "max_lifetime_seconds",
                    lifecycle.get("max_lifetime_seconds"),
                ),
                "max_lifetime_seconds",
            ),
            encoding=str(config.get("encoding", "utf-8")),
            encoding_error_handler=encoding_errors,
            supports_parallel_tool_calls=self._bool(
                config.get("supports_parallel_tool_calls"),
                False,
            ),
            tools=self._mapping(config.get("tools"), "tools"),
            sampling=self._mapping(config.get("sampling"), "sampling"),
            elicitation=self._mapping(config.get("elicitation"), "elicitation"),
            lifecycle=lifecycle,
            metadata=metadata,
        )

    def load_servers(
        self,
        path: str | os.PathLike[str],
        *,
        key: str = "mcp_servers",
        include_disabled: bool = False,
    ) -> dict[str, MCPServerConfig]:
        """Load, interpolate, and normalize a server mapping."""
        if self.safe_mode:
            return {}
        document = self.load_document(path)
        raw_servers = document.get(key, document if key == "" else None)
        if raw_servers is None:
            return {}
        if not isinstance(raw_servers, Mapping):
            raise MCPConfigError(f"Configuration key {key!r} must be a mapping.")
        servers: dict[str, MCPServerConfig] = {}
        for name, value in raw_servers.items():
            normalized = self.normalize_server(str(name), value)
            if normalized.enabled or include_disabled:
                servers[normalized.name] = normalized
        return servers

def capability_profile(capability_id, changes):
    """Tell the process this tool needs a tool resource."""
    from kernel.process.declaration import ProcessDeclaration, ResourceClaim
    from kernel.resource.definition import ResourceKind

    return ProcessDeclaration(
        capability=capability_id,
        resources=(
            ResourceClaim(kind=ResourceKind.TOOL, identity={"id": capability_id}),
        ),
    )

