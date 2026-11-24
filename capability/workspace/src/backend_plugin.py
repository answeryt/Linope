# -*- coding: utf-8 -*-
"""Docker container I/O: exec, get_archive, put_archive.

aiodocker is imported only on a 404 path that needs DockerError, and the
container object is injected so tests never talk to a daemon.
"""

from __future__ import annotations

import asyncio
import io
import posixpath
import tarfile
from typing import Any, NamedTuple


PLUGIN_NAME = "sandbox_workspace_backend"
PLUGIN_VERSION = "1.0"


class ExecResult(NamedTuple):
    exit_code: int
    stdout: bytes
    stderr: bytes

    def ok(self) -> bool:
        return self.exit_code == 0


class DockerBackend:
    """Three primitives over a started aiodocker container."""

    def __init__(self, container: Any, workdir: str) -> None:
        self._container = container
        self._workdir = workdir

    async def getcwd(self) -> str:
        return self._workdir

    def join_path(self, *parts: str) -> str:
        return posixpath.join(*parts)

    async def exec_shell(
        self,
        command: list[str],
        *,
        cwd: str | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        """Run argv via container exec. Shell features need ``sh -c``."""

        async def _run() -> ExecResult:
            exec_obj = await self._container.exec(
                cmd=command,
                workdir=cwd or self._workdir,
            )
            stdout_parts: list[bytes] = []
            stderr_parts: list[bytes] = []
            async with exec_obj.start() as stream:
                while True:
                    msg = await stream.read_out()
                    if msg is None:
                        break
                    if msg.stream == 1:
                        stdout_parts.append(msg.data)
                    else:
                        stderr_parts.append(msg.data)
            inspect = await exec_obj.inspect()
            code = inspect.get("ExitCode", -1)
            if code is None:
                code = -1
            return ExecResult(
                exit_code=int(code),
                stdout=b"".join(stdout_parts),
                stderr=b"".join(stderr_parts),
            )

        if timeout is None:
            return await _run()
        try:
            return await asyncio.wait_for(_run(), timeout=timeout)
        except asyncio.TimeoutError:
            return ExecResult(exit_code=-1, stdout=b"", stderr=b"timed out")

    async def read_file(self, path: str) -> bytes:
        try:
            archive = await self._container.get_archive(path)
        except Exception as exc:
            if getattr(exc, "status", None) == 404:
                raise FileNotFoundError(f"not found in container: {path}") from exc
            raise
        try:
            for member in archive.getmembers():
                if member.isfile():
                    handle = archive.extractfile(member)
                    if handle is not None:
                        return handle.read()
        finally:
            archive.close()
        raise FileNotFoundError(f"not found in container: {path}")

    async def write_file(self, path: str, data: bytes) -> None:
        parent = posixpath.dirname(path) or "/"
        name = posixpath.basename(path)
        await self.exec_shell(["mkdir", "-p", parent])
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        await self._container.put_archive(parent, buf.getvalue())


def build_backend(container: Any, workdir: str) -> DockerBackend:
    return DockerBackend(container, workdir)
