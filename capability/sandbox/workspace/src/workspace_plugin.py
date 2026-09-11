# -*- coding: utf-8 -*-
"""Docker workspace: hashed image, long-lived container, optional bind-mount.

Host injects ``prepare_build_context`` and ``build_backend`` so this file
never imports the dockerfile or backend siblings. aiodocker is constructed
lazily (or replaced in tests via ``docker_client``).
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import sys
import tarfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any


PLUGIN_NAME = "sandbox_workspace"
PLUGIN_VERSION = "1.0"

# Duplicated locally; Host injects dockerfile helpers instead of importing them.
DEFAULT_BASE_IMAGE = "python:3.11-slim"
CONTAINER_WORKDIR = "/workspace"
DEFAULT_INSTRUCTIONS = (
    "{backend} workspace at {workdir}. "
    "File and command work runs inside the container."
)

logger = logging.getLogger(PLUGIN_NAME)

PrepareBuildContext = Callable[..., tuple[Path, str, dict[str, bytes]]]
BuildBackend = Callable[[Any, str], Any]
DockerClientFactory = Callable[[], Any]


def _default_docker_client() -> Any:
    import aiodocker

    return aiodocker.Docker()


class DockerWorkspace:
    """Workspace backed by a Docker container.

    The workspace is not started in ``__init__`` — call :meth:`initialize`
    or use the object as an async context manager.
    """

    def __init__(
        self,
        *,
        prepare_build_context: PrepareBuildContext,
        build_backend: BuildBackend,
        docker_client: DockerClientFactory | None = None,
        workspace_id: str | None = None,
        base_image: str = DEFAULT_BASE_IMAGE,
        host_workdir: str | None = None,
        node_version: str | None = None,
        extra_pip: list[str] | None = None,
        env: dict[str, str] | None = None,
        instructions: str = DEFAULT_INSTRUCTIONS,
        **kwargs: Any,
    ) -> None:
        if prepare_build_context is None or build_backend is None:
            raise TypeError("prepare_build_context and build_backend are required")
        if "workdir" in kwargs:
            logger.warning(
                "DockerWorkspace parameter 'workdir' is deprecated, "
                "use 'host_workdir' instead.",
            )
            if host_workdir is None:
                host_workdir = kwargs.pop("workdir")
        self._prepare_build_context = prepare_build_context
        self._build_backend = build_backend
        self._make_docker_client = docker_client or _default_docker_client
        self.workspace_id = workspace_id or uuid.uuid4().hex
        self.workdir = CONTAINER_WORKDIR
        self.base_image = base_image
        self.host_workdir = host_workdir
        self.node_version = node_version
        self.extra_pip: list[str] = list(extra_pip or [])
        self.env: dict[str, str] = dict(env or {})
        self.instructions = instructions.format(
            backend="Docker-based",
            workdir=self.workdir,
        )
        self.is_alive = False
        self._client: Any = None
        self._container: Any = None
        self._backend: Any = None
        self._image_tag: str = ""

    @property
    def is_persistent(self) -> bool:
        return self.host_workdir is not None

    def get_backend(self) -> Any:
        if self._backend is None:
            raise RuntimeError("workspace is not initialized")
        return self._backend

    async def get_instructions(self) -> str:
        return self.instructions

    async def initialize(self) -> None:
        if self.is_alive:
            return
        await self._provision_backend()
        if self._backend is None:
            raise RuntimeError("_provision_backend must set self._backend")
        await self._backend.exec_shell(["mkdir", "-p", self.workdir], cwd="/")
        self.is_alive = True

    async def close(self) -> None:
        try:
            await self._teardown_backend()
        finally:
            self._backend = None
            self.is_alive = False

    async def __aenter__(self) -> "DockerWorkspace":
        await self.initialize()
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        await self.close()
        return False

    async def _provision_backend(self) -> None:
        self._client = self._make_docker_client()
        await self._build_or_reuse_image()
        await self._create_and_start_container()

    async def _teardown_backend(self) -> None:
        if self._container is not None:
            # Native Linux Docker writes bind-mount files as the container
            # root uid; restore the host user so teardown can delete them.
            # Desktop Docker on macOS/Windows remaps uids itself.
            if (
                self.host_workdir is not None
                and sys.platform == "linux"
                and self._backend is not None
            ):
                try:
                    await self._backend.exec_shell(
                        [
                            "chown",
                            "-R",
                            f"{os.getuid()}:{os.getgid()}",
                            CONTAINER_WORKDIR,
                        ],
                        timeout=10.0,
                    )
                except Exception:
                    pass
            try:
                await self._container.kill()
            except Exception:
                pass
            try:
                await self._container.delete(force=True)
            except Exception:
                pass
            self._container = None

        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None

    async def _build_or_reuse_image(self) -> None:
        ctx_dir, tag, _ = self._prepare_build_context(
            base_image=self.base_image,
            container_workdir=self.workdir,
            node_version=self.node_version,
            extra_pip=self.extra_pip,
        )
        self._image_tag = tag
        try:
            try:
                await self._client.images.inspect(tag)
                logger.info("DockerWorkspace: image cache hit %r", tag)
                return
            except Exception:
                pass

            logger.info("DockerWorkspace: building image %r", tag)
            # aiodocker's build API wants a tar body; docker-py would tar
            # ``path=`` for us. ``arcname="."`` keeps Dockerfile at tar root.
            tar_buf = io.BytesIO()
            with tarfile.open(fileobj=tar_buf, mode="w") as tf:
                tf.add(str(ctx_dir), arcname=".")
            tar_buf.seek(0)
            # ``encoding="identity"`` keeps the tar uncompressed. aiodocker
            # would otherwise gzip it and the daemon would reject the stream.
            stream = self._client.images.build(
                fileobj=tar_buf,
                encoding="identity",
                tag=tag,
                stream=True,
                rm=True,
            )
            tail: list[str] = []
            tail_max = 200
            async for chunk in stream:
                if not isinstance(chunk, dict):
                    continue
                if "stream" in chunk:
                    msg = str(chunk["stream"]).rstrip()
                    if msg:
                        logger.debug("[docker build] %s", msg)
                        tail.append(msg)
                        if len(tail) > tail_max:
                            del tail[: len(tail) - tail_max]
                if "error" in chunk:
                    log = "\n".join(tail)
                    raise RuntimeError(
                        f"docker build failed: {chunk['error']}\n"
                        f"--- last {len(tail)} build log lines ---\n"
                        f"{log}",
                    )
        finally:
            logger.info("DockerWorkspace: finish building image %r", tag)
            shutil.rmtree(ctx_dir, ignore_errors=True)

    async def _create_and_start_container(self) -> None:
        config: dict[str, Any] = {
            "Image": self._image_tag,
            "Cmd": ["sleep", "infinity"],
            "WorkingDir": CONTAINER_WORKDIR,
            "Labels": {
                "sandbox.workspace": "true",
                "sandbox.workspace.id": self.workspace_id,
            },
        }
        if self.env:
            config["Env"] = [f"{key}={value}" for key, value in self.env.items()]

        host_config: dict[str, Any] = {}
        if self.host_workdir is not None:
            os.makedirs(self.host_workdir, exist_ok=True)
            host_config["Binds"] = [
                f"{os.path.abspath(self.host_workdir)}:{CONTAINER_WORKDIR}:rw",
            ]
        config["HostConfig"] = host_config

        self._container = await self._client.containers.create_or_replace(
            name=f"sb_ws_{self.workspace_id}",
            config=config,
        )
        await self._container.start()
        self._backend = self._build_backend(self._container, CONTAINER_WORKDIR)


def build_workspace(
    *,
    prepare_build_context: PrepareBuildContext,
    build_backend: BuildBackend,
    docker_client: DockerClientFactory | None = None,
    workspace_id: str | None = None,
    base_image: str = DEFAULT_BASE_IMAGE,
    host_workdir: str | None = None,
    node_version: str | None = None,
    extra_pip: list[str] | None = None,
    env: dict[str, str] | None = None,
    instructions: str = DEFAULT_INSTRUCTIONS,
    **kwargs: Any,
) -> DockerWorkspace:
    """Host entry: inject image-context and backend factories."""
    return DockerWorkspace(
        prepare_build_context=prepare_build_context,
        build_backend=build_backend,
        docker_client=docker_client,
        workspace_id=workspace_id,
        base_image=base_image,
        host_workdir=host_workdir,
        node_version=node_version,
        extra_pip=extra_pip,
        env=env,
        instructions=instructions,
        **kwargs,
    )
