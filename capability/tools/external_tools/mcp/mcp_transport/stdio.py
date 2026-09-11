# -*- coding: utf-8 -*-
"""Standalone stdio MCP connection plugin.

This module owns one stdio connection attempt. It imports no sibling project
module and can be loaded directly from its file path.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Mapping, TextIO

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


TRANSPORT = "stdio"

_SAFE_ENV_KEYS = {
    "APPDATA",
    "COMSPEC",
    "HOME",
    "HOMEDRIVE",
    "HOMEPATH",
    "LANG",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SHELL",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USER",
    "USERPROFILE",
    "WINDIR",
}


class InvalidMCPConfiguration(ValueError):
    """Raised when a stdio MCP configuration is invalid."""


class MCPClientConnect:
    """Open and initialize one MCP session over stdio."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        session_kwargs: Mapping[str, Any] | None = None,
        errlog: TextIO | None = None,
    ) -> None:
        self.config = dict(config)
        self.session_kwargs = dict(session_kwargs or {})
        self.errlog = errlog if errlog is not None else sys.stderr
        self.initialize_result: Any = None

        command = self.config.get("command")
        if not isinstance(command, str) or not command.strip():
            raise InvalidMCPConfiguration(
                "Stdio MCP configuration must contain a non-empty 'command'.",
            )

    @property
    def transport(self) -> str:
        """Return the transport implemented by this plugin."""
        return TRANSPORT

    def _stdio_environment(self) -> dict[str, str]:
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() in _SAFE_ENV_KEYS or key.startswith("XDG_")
        }
        configured = self.config.get("env")
        if configured:
            environment.update(
                {str(key): str(value) for key, value in dict(configured).items()},
            )
        return environment

    @staticmethod
    def _resolve_command(
        command: str,
        environment: dict[str, str],
    ) -> tuple[str, dict[str, str]]:
        expanded = os.path.expanduser(command.strip())
        resolved = shutil.which(expanded, path=environment.get("PATH"))
        if resolved:
            expanded = resolved

        command_dir = os.path.dirname(expanded)
        if command_dir:
            current_path = environment.get("PATH", "")
            path_parts = [part for part in current_path.split(os.pathsep) if part]
            if command_dir not in path_parts:
                environment["PATH"] = os.pathsep.join([command_dir, *path_parts])
        return expanded, environment

    @asynccontextmanager
    async def _initialized_session(
        self,
        read_stream: Any,
        write_stream: Any,
    ) -> AsyncIterator[ClientSession]:
        async with ClientSession(
            read_stream,
            write_stream,
            **self.session_kwargs,
        ) as session:
            connect_timeout = float(self.config.get("connect_timeout", 60.0))
            self.initialize_result = await asyncio.wait_for(
                session.initialize(),
                timeout=connect_timeout,
            )
            yield session

    @asynccontextmanager
    async def open(self) -> AsyncIterator[ClientSession]:
        """Open and initialize exactly one stdio MCP session."""
        self.initialize_result = None
        environment = self._stdio_environment()
        command, environment = self._resolve_command(
            str(self.config["command"]),
            environment,
        )
        parameters = StdioServerParameters(
            command=command,
            args=[str(arg) for arg in self.config.get("args", [])],
            env=environment,
            cwd=self.config.get("cwd"),
            encoding=str(self.config.get("encoding", "utf-8")),
            encoding_error_handler=self.config.get(
                "encoding_error_handler",
                "strict",
            ),
        )
        async with stdio_client(parameters, errlog=self.errlog) as streams:
            async with self._initialized_session(*streams) as session:
                yield session
