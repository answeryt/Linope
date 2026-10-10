# -*- coding: utf-8 -*-
"""Standalone MCP authentication recovery and security plugin."""

from __future__ import annotations

import asyncio
import ipaddress
import inspect
import os
import re
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping
from urllib.parse import urlparse


PLUGIN_NAME = "mcp_auth_security"
PLUGIN_VERSION = "1.0"

_SAFE_ENV_KEYS = {
    "APPDATA", "COMSPEC", "HOME", "HOMEDRIVE", "HOMEPATH", "LANG",
    "LOCALAPPDATA", "PATH", "PATHEXT", "SHELL", "SYSTEMDRIVE",
    "SYSTEMROOT", "TEMP", "TMP", "USER", "USERPROFILE", "WINDIR",
}
_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")
_CREDENTIAL_PATTERN = re.compile(
    r"(?:"
    r"gh[opsu]_[A-Za-z0-9_]{1,255}"
    r"|sk-[A-Za-z0-9_-]{8,255}"
    r"|Bearer\s+\S+"
    r"|(?:token|key|api[_-]?key|password|secret)"
    r"\s*[=:]\s*[^\s&,;\"']{1,255}"
    r")",
    re.IGNORECASE,
)
_INJECTION_PATTERNS = (
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.I), "prompt override"),
    (re.compile(r"you\s+are\s+now\s+a", re.I), "identity override"),
    (re.compile(r"your\s+new\s+(task|role|instructions?)\s+(is|are)", re.I), "task override"),
    (re.compile(r"system\s*:\s*", re.I), "system prompt injection"),
    (re.compile(r"<\s*(system|human|assistant)\s*>", re.I), "role tag injection"),
    (re.compile(r"do\s+not\s+(tell|inform|mention|reveal)", re.I), "concealment instruction"),
    (re.compile(r"(curl|wget|fetch)\s+https?://", re.I), "network command"),
    (re.compile(r"\b(exec|eval)\s*\(", re.I), "code execution reference"),
    (re.compile(r"import\s+(subprocess|os|shutil|socket)", re.I), "dangerous import"),
)


class InvalidMCPServerConfiguration(ValueError):
    """Raised when security validation rejects a server configuration."""


class MCPAuthenticationRequired(PermissionError):
    """Raised when automatic authentication recovery is unavailable."""


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class MCPAuthSecurityPlugin:
    """Validate endpoints, contain secrets, and recover authentication once."""

    def __init__(
        self,
        *,
        secret_getter: Callable[[str, Any], Any] | None = None,
        recovery_timeout: float = 15.0,
        require_https: bool = False,
        block_private_networks: bool = False,
    ) -> None:
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive.")
        self.secret_getter = secret_getter
        self.recovery_timeout = recovery_timeout
        self.require_https = require_https
        self.block_private_networks = block_private_networks

    @staticmethod
    def sanitize_error(value: Any) -> str:
        """Remove credential-shaped values before logging or model exposure."""
        return _CREDENTIAL_PATTERN.sub("[REDACTED]", str(value))

    @staticmethod
    def safe_environment(
        configured: Mapping[str, Any] | None = None,
        *,
        source: Mapping[str, str] | None = None,
        extra_allowed: set[str] | None = None,
    ) -> dict[str, str]:
        """Build a least-privilege environment for stdio MCP subprocesses."""
        source = source if source is not None else os.environ
        allowed = {key.upper() for key in (extra_allowed or set())}
        environment = {
            str(key): str(value)
            for key, value in source.items()
            if key.upper() in _SAFE_ENV_KEYS
            or key.upper() in allowed
            or key.startswith("XDG_")
        }
        if configured:
            environment.update(
                {str(key): str(value) for key, value in configured.items()},
            )
        return environment

    def interpolate(self, value: Any) -> Any:
        """Resolve ``${VAR}`` and ``${env:VAR}`` recursively."""
        if isinstance(value, str):
            def replace(match: re.Match[str]) -> str:
                name = match.group(1).strip()
                if name.startswith("env:"):
                    name = name[4:].strip()
                fallback = match.group(0)
                if self.secret_getter is not None:
                    resolved = self.secret_getter(name, fallback)
                else:
                    resolved = os.environ.get(name, fallback)
                return fallback if resolved is None else str(resolved)

            return _ENV_PATTERN.sub(replace, value)
        if isinstance(value, dict):
            return {key: self.interpolate(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.interpolate(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.interpolate(item) for item in value)
        return value

    def validate_url(self, server_name: str, value: Any) -> str:
        """Validate an absolute HTTP(S) MCP endpoint."""
        if not isinstance(value, str) or not value.strip():
            raise InvalidMCPServerConfiguration(
                f"MCP server {server_name!r} requires a non-empty URL.",
            )
        url = value.strip()
        parsed = urlparse(url)
        if parsed.scheme.lower() not in {"http", "https"}:
            raise InvalidMCPServerConfiguration(
                f"MCP server {server_name!r} URL must use http or https.",
            )
        if not parsed.netloc or not parsed.hostname:
            raise InvalidMCPServerConfiguration(
                f"MCP server {server_name!r} URL is missing a hostname.",
            )
        if parsed.username is not None or parsed.password is not None:
            raise InvalidMCPServerConfiguration(
                f"MCP server {server_name!r} URL must not contain credentials.",
            )
        if parsed.fragment:
            raise InvalidMCPServerConfiguration(
                f"MCP server {server_name!r} URL must not contain a fragment.",
            )
        if any(ord(character) < 32 for character in url):
            raise InvalidMCPServerConfiguration(
                f"MCP server {server_name!r} URL contains control characters.",
            )
        if self.require_https and parsed.scheme.lower() != "https":
            raise InvalidMCPServerConfiguration(
                f"MCP server {server_name!r} requires HTTPS.",
            )
        if self.block_private_networks:
            try:
                address = ipaddress.ip_address(parsed.hostname)
            except ValueError:
                address = None
            if address is not None and (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_reserved
            ):
                raise InvalidMCPServerConfiguration(
                    f"MCP server {server_name!r} URL targets a private address.",
                )
        return url

    @staticmethod
    def resolve_client_certificate(
        server_name: str,
        config: Mapping[str, Any],
    ) -> str | tuple[str, str] | tuple[str, str, str] | None:
        """Resolve and verify combined or split mTLS certificate files."""
        raw_cert = config.get("client_cert")
        raw_key = config.get("client_key")
        if raw_cert is None and raw_key is None:
            return None

        def expand(value: Any, label: str) -> str:
            if not isinstance(value, str) or not value.strip():
                raise InvalidMCPServerConfiguration(
                    f"{server_name}: {label} must be a non-empty path.",
                )
            path = Path(value.strip()).expanduser()
            if not path.is_file():
                raise FileNotFoundError(f"{server_name}: {label} not found: {path}")
            return str(path.resolve())

        if isinstance(raw_cert, (list, tuple)):
            if raw_key is not None or len(raw_cert) not in {2, 3}:
                raise InvalidMCPServerConfiguration(
                    f"{server_name}: client_cert list must contain cert/key "
                    "or cert/key/password and cannot be combined with client_key.",
                )
            cert = expand(raw_cert[0], "client_cert[0]")
            key = expand(raw_cert[1], "client_cert[1]")
            if len(raw_cert) == 3:
                if not isinstance(raw_cert[2], str):
                    raise InvalidMCPServerConfiguration(
                        f"{server_name}: certificate password must be a string.",
                    )
                return cert, key, raw_cert[2]
            return cert, key

        cert = expand(raw_cert, "client_cert")
        return (cert, expand(raw_key, "client_key")) if raw_key is not None else cert

    @staticmethod
    def scan_description(description: str) -> list[str]:
        """Return prompt-injection indicators found in tool metadata."""
        return [
            reason
            for pattern, reason in _INJECTION_PATTERNS
            if pattern.search(description or "")
        ]

    def validate_server(
        self,
        server_name: str,
        config: Mapping[str, Any],
        *,
        reject_suspicious: bool = True,
    ) -> list[str]:
        """Validate transport shape and report exfiltration indicators."""
        if not isinstance(config, Mapping):
            raise InvalidMCPServerConfiguration(
                f"MCP server {server_name!r} configuration must be a mapping.",
            )
        has_url = "url" in config
        has_command = bool(str(config.get("command", "")).strip())
        if has_url == has_command:
            raise InvalidMCPServerConfiguration(
                f"MCP server {server_name!r} must specify exactly one of "
                "'url' or 'command'.",
            )
        if has_url:
            self.validate_url(server_name, config["url"])
        self.resolve_client_certificate(server_name, config)

        findings: list[str] = []
        joined = " ".join(
            [str(config.get("command", ""))]
            + [str(arg) for arg in config.get("args", []) or []],
        )
        if re.search(r"\b(curl|wget|powershell|cmd)\b.*https?://", joined, re.I):
            findings.append("command launches a network-capable shell/downloader")
        if re.search(r"\$\{(?:env:)?(?:PATH|HOME|USERPROFILE)\}", joined, re.I):
            findings.append("command interpolates broad host environment paths")
        if findings and reject_suspicious:
            raise InvalidMCPServerConfiguration(
                f"Suspicious MCP server {server_name!r}: {'; '.join(findings)}",
            )
        return findings

    @staticmethod
    def is_auth_error(error: BaseException) -> bool:
        """Recognize SDK OAuth failures and HTTP 401/403 responses."""
        stack: list[BaseException | None] = [error]
        seen: set[int] = set()
        while stack and len(seen) < 1000:
            current = stack.pop()
            if current is None or id(current) in seen:
                continue
            seen.add(id(current))
            status = getattr(getattr(current, "response", None), "status_code", None)
            name = type(current).__name__.lower()
            text = str(current).lower()
            if status in {401, 403} or any(
                marker in name or marker in text
                for marker in ("unauthorized", "oauthflow", "oauthtoken")
            ):
                return True
            stack.extend(getattr(current, "exceptions", ()) or ())
            stack.append(getattr(current, "__cause__", None))
            stack.append(getattr(current, "__context__", None))
        return False

    async def recover_and_retry(
        self,
        operation: Callable[[], Any | Awaitable[Any]],
        error: BaseException,
        *,
        refresh_auth: Callable[[], Any | Awaitable[Any]],
        reconnect: Callable[[], Any | Awaitable[Any]],
    ) -> Any:
        """Refresh credentials, rebuild the transport, and retry exactly once."""
        if not self.is_auth_error(error):
            raise error
        try:
            recovered = await asyncio.wait_for(
                _maybe_await(refresh_auth()),
                timeout=self.recovery_timeout,
            )
            if not recovered:
                raise MCPAuthenticationRequired(
                    "MCP authentication refresh was rejected.",
                )
            reconnected = await asyncio.wait_for(
                _maybe_await(reconnect()),
                timeout=self.recovery_timeout,
            )
            if reconnected is False:
                raise MCPAuthenticationRequired(
                    "MCP transport did not reconnect after authentication refresh.",
                )
            return await _maybe_await(operation())
        except MCPAuthenticationRequired:
            raise
        except asyncio.TimeoutError as timeout:
            raise MCPAuthenticationRequired(
                "MCP authentication recovery timed out.",
            ) from timeout

    @staticmethod
    def redirect_guard(
        original_url: str,
        *,
        sensitive_headers: tuple[str, ...] = (
            "Authorization",
            "Proxy-Authorization",
            "Cookie",
            "X-API-Key",
        ),
    ) -> Callable[[Any], Awaitable[None]]:
        """Build an httpx hook that strips cross-origin credentials."""
        origin = urlparse(original_url)

        async def guard(response: Any) -> None:
            next_request = getattr(response, "next_request", None)
            if not getattr(response, "is_redirect", False) or next_request is None:
                return
            target = urlparse(str(next_request.url))
            if (target.scheme, target.hostname, target.port) != (
                origin.scheme,
                origin.hostname,
                origin.port,
            ):
                for header in sensitive_headers:
                    next_request.headers.pop(header, None)

        return guard

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

