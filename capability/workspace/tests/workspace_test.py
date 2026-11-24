# -*- coding: utf-8 -*-
"""Pin Docker workspace lifecycle without a daemon. Load plugins by file."""

from __future__ import annotations

import asyncio
import io
import os
import tarfile
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch


def _load(name: str, filename: str):
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "src" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Msg:
    def __init__(self, stream: int, data: bytes) -> None:
        self.stream = stream
        self.data = data


class _ExecStream:
    def __init__(self, chunks: list[_Msg] | None = None, hang: bool = False) -> None:
        self._chunks = list(chunks or [])
        self._hang = hang

    async def __aenter__(self) -> "_ExecStream":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def read_out(self) -> _Msg | None:
        if self._hang:
            await asyncio.sleep(30)
            return None
        if not self._chunks:
            return None
        return self._chunks.pop(0)


class _Exec:
    def __init__(self, cmd: list[str], workdir: str | None, hang: bool = False) -> None:
        self.cmd = cmd
        self.workdir = workdir
        self.exit_code = 0
        self._hang = hang

    def start(self) -> _ExecStream:
        if self._hang:
            return _ExecStream(hang=True)
        return _ExecStream([_Msg(1, b"out"), _Msg(2, b"err")])

    async def inspect(self) -> dict[str, Any]:
        return {"ExitCode": self.exit_code}


class _StatusError(Exception):
    def __init__(self, status: int) -> None:
        self.status = status


class _FakeContainer:
    def __init__(self, name: str = "c", config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}
        self.started = False
        self.killed = False
        self.deleted = False
        self.execs: list[tuple[list[str], str | None]] = []
        self.puts: list[tuple[str, bytes]] = []
        self.archive_files: dict[str, bytes] = {}
        self.hang_exec = False

    async def start(self) -> None:
        self.started = True

    async def kill(self) -> None:
        self.killed = True

    async def delete(self, force: bool = False) -> None:
        self.deleted = True

    async def exec(self, cmd: list[str], workdir: str | None = None) -> _Exec:
        self.execs.append((list(cmd), workdir))
        return _Exec(list(cmd), workdir, hang=self.hang_exec)

    async def get_archive(self, path: str) -> tarfile.TarFile:
        if path not in self.archive_files:
            raise _StatusError(404)
        data = self.archive_files[path]
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            info = tarfile.TarInfo(name=os.path.basename(path) or "file")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        buf.seek(0)
        return tarfile.open(fileobj=buf, mode="r")

    async def put_archive(self, parent: str, payload: bytes) -> None:
        self.puts.append((parent, payload))


class _FakeImages:
    def __init__(self) -> None:
        self.tags: set[str] = set()
        self.builds: list[dict[str, Any]] = []
        self.fail_error: str | None = None

    async def inspect(self, tag: str) -> dict[str, str]:
        if tag not in self.tags:
            raise RuntimeError("missing")
        return {"Id": tag}

    def build(self, **kwargs: Any):
        self.builds.append(kwargs)
        tag = kwargs["tag"]

        async def _stream():
            yield {"stream": "Step 1/1 : FROM python"}
            if self.fail_error:
                yield {"error": self.fail_error}
                return
            self.tags.add(tag)
            yield {"aux": {"ID": "sha256:test"}}

        return _stream()


class _FakeContainers:
    def __init__(self) -> None:
        self.items: list[_FakeContainer] = []

    async def create_or_replace(self, name: str, config: dict[str, Any]) -> _FakeContainer:
        container = _FakeContainer(name, config)
        self.items.append(container)
        return container


class _FakeDocker:
    def __init__(self) -> None:
        self.images = _FakeImages()
        self.containers = _FakeContainers()
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeBackend:
    def __init__(self, container: Any, workdir: str) -> None:
        self.container = container
        self.workdir = workdir
        self.shell: list[list[str]] = []

    async def exec_shell(
        self,
        command: list[str],
        *,
        cwd: str | None = None,
        timeout: float | None = None,
    ) -> SimpleNamespace:
        self.shell.append(list(command))
        return SimpleNamespace(exit_code=0, stdout=b"", stderr=b"")


def _prepare_factory(tag: str = "sandbox-workspace:testhash"):
    calls: list[dict[str, Any]] = []

    def prepare_build_context(**kwargs: Any):
        calls.append(dict(kwargs))
        ctx = Path(tempfile.mkdtemp(prefix="ws-test-"))
        (ctx / "Dockerfile").write_text("FROM python:3.11-slim\nWORKDIR /workspace\n")
        return ctx, tag, {}

    return prepare_build_context, calls


def _workspace(**config: Any):
    dockerfile = _load("sandbox_workspace_dockerfile", "dockerfile_plugin.py")
    backend = _load("sandbox_workspace_backend", "backend_plugin.py")
    plugin = _load("sandbox_workspace", "workspace_plugin.py")
    client = config.pop("docker_client", None)
    if client is None:
        fake = _FakeDocker()
        client = lambda: fake  # noqa: E731
    else:
        fake = None
    ws = plugin.build_workspace(
        prepare_build_context=config.pop("prepare_build_context", dockerfile.prepare_build_context),
        build_backend=config.pop("build_backend", backend.build_backend),
        docker_client=client,
        **config,
    )
    return plugin, dockerfile, backend, ws, fake


def test_plugin_identity() -> None:
    dockerfile = _load("sandbox_workspace_dockerfile", "dockerfile_plugin.py")
    backend = _load("sandbox_workspace_backend", "backend_plugin.py")
    plugin = _load("sandbox_workspace", "workspace_plugin.py")
    assert dockerfile.PLUGIN_NAME == "sandbox_workspace_dockerfile"
    assert backend.PLUGIN_NAME == "sandbox_workspace_backend"
    assert plugin.PLUGIN_NAME == "sandbox_workspace"
    assert dockerfile.CONTAINER_WORKDIR == plugin.CONTAINER_WORKDIR


def test_image_tag_is_stable_and_tracks_inputs() -> None:
    dockerfile = _load("sandbox_workspace_dockerfile", "dockerfile_plugin.py")
    first = dockerfile.compute_image_tag(dockerfile.render_dockerfile())
    second = dockerfile.compute_image_tag(dockerfile.render_dockerfile())
    pip_tag = dockerfile.compute_image_tag(
        dockerfile.render_dockerfile(extra_pip=["httpx"]),
    )
    node_text = dockerfile.render_dockerfile(node_version="20")
    assert first == second
    assert first != pip_tag
    assert first.startswith("sandbox-workspace:")
    assert "FROM node:20-slim AS node_stage" in node_text
    assert "WORKDIR /workspace" in node_text


def test_prepare_build_context_writes_dockerfile() -> None:
    dockerfile = _load("sandbox_workspace_dockerfile", "dockerfile_plugin.py")
    ctx_dir, tag, copy_files = dockerfile.prepare_build_context(extra_pip=["httpx"])
    try:
        text = (ctx_dir / "Dockerfile").read_text(encoding="utf-8")
        assert "pip install --no-cache-dir" in text
        assert "httpx" in text
        assert tag == dockerfile.compute_image_tag(text, copy_files)
        assert copy_files == {}
    finally:
        import shutil

        shutil.rmtree(ctx_dir, ignore_errors=True)


def test_backend_exec_read_write() -> None:
    async def _run() -> None:
        backend_mod = _load("sandbox_workspace_backend", "backend_plugin.py")
        container = _FakeContainer()
        container.archive_files["/workspace/a.txt"] = b"hello"
        backend = backend_mod.build_backend(container, "/workspace")
        result = await backend.exec_shell(["echo", "hi"])
        assert result.exit_code == 0
        assert result.stdout == b"out"
        assert result.stderr == b"err"
        assert container.execs[0] == (["echo", "hi"], "/workspace")
        assert await backend.read_file("/workspace/a.txt") == b"hello"
        await backend.write_file("/workspace/dir/b.txt", b"data")
        assert container.execs[-1][0] == ["mkdir", "-p", "/workspace/dir"]
        assert container.puts[0][0] == "/workspace/dir"
        try:
            await backend.read_file("/missing")
        except FileNotFoundError as exc:
            assert "missing" in str(exc)
        else:
            raise AssertionError("expected missing file")

    asyncio.run(_run())


def test_backend_exec_timeout() -> None:
    async def _run() -> None:
        backend_mod = _load("sandbox_workspace_backend", "backend_plugin.py")
        container = _FakeContainer()
        container.hang_exec = True
        backend = backend_mod.build_backend(container, "/workspace")
        result = await backend.exec_shell(["sleep", "9"], timeout=0.05)
        assert result.exit_code == -1
        assert result.stderr == b"timed out"

    asyncio.run(_run())


def test_ephemeral_container_config() -> None:
    async def _run() -> None:
        _plugin, _df, _be, ws, fake = _workspace(workspace_id="abc123", env={"FOO": "bar"})
        assert fake is not None
        await ws.initialize()
        assert ws.is_alive
        assert not ws.is_persistent
        container = fake.containers.items[0]
        assert container.started
        assert container.name == "sb_ws_abc123"
        assert container.config["Cmd"] == ["sleep", "infinity"]
        assert container.config["WorkingDir"] == "/workspace"
        assert container.config["Env"] == ["FOO=bar"]
        assert container.config["Labels"]["sandbox.workspace"] == "true"
        assert container.config["Labels"]["sandbox.workspace.id"] == "abc123"
        assert container.config["HostConfig"] == {}
        assert ws.get_backend() is not None
        await ws.close()
        assert container.killed and container.deleted and fake.closed
        assert not ws.is_alive

    asyncio.run(_run())


def test_persistent_bind_mount_and_cache_hit() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as host:
            prepare, calls = _prepare_factory("sandbox-workspace:cached")
            fake = _FakeDocker()
            fake.images.tags.add("sandbox-workspace:cached")
            _plugin, _df, _be, ws, _ = _workspace(
                workspace_id="persist",
                host_workdir=host,
                prepare_build_context=prepare,
                docker_client=lambda: fake,
                extra_pip=["httpx"],
                node_version="20",
            )
            await ws.initialize()
            assert ws.is_persistent
            assert fake.images.builds == []
            assert calls[0]["extra_pip"] == ["httpx"]
            assert calls[0]["node_version"] == "20"
            binds = fake.containers.items[0].config["HostConfig"]["Binds"]
            assert binds == [f"{os.path.abspath(host)}:/workspace:rw"]
            await ws.close()

    asyncio.run(_run())


def test_build_failure_includes_log_tail() -> None:
    async def _run() -> None:
        prepare, _calls = _prepare_factory()
        fake = _FakeDocker()
        fake.images.fail_error = "command returned non-zero code: 1"
        _plugin, _df, _be, ws, _ = _workspace(
            prepare_build_context=prepare,
            docker_client=lambda: fake,
        )
        try:
            await ws.initialize()
        except RuntimeError as exc:
            assert "docker build failed" in str(exc)
            assert "Step 1/1" in str(exc)
        else:
            raise AssertionError("expected build failure")

    asyncio.run(_run())


def test_legacy_workdir_kwarg() -> None:
    import logging

    with tempfile.TemporaryDirectory() as host:
        with patch.object(logging.getLogger("sandbox_workspace"), "warning"):
            _plugin, _df, _be, ws, _fake = _workspace(workdir=host)
        assert ws.host_workdir == host
        assert "Docker-based" in ws.instructions
        assert "/workspace" in ws.instructions


def test_linux_teardown_chowns_bind_mount() -> None:
    async def _run() -> None:
        with tempfile.TemporaryDirectory() as host:
            fake = _FakeDocker()
            backend = _FakeBackend(None, "/workspace")
            plugin, _df, _be, ws, _ = _workspace(
                host_workdir=host,
                docker_client=lambda: fake,
                build_backend=lambda container, workdir: backend,
            )
            with (
                patch.object(plugin.sys, "platform", "linux"),
                patch.object(plugin.os, "getuid", create=True, return_value=1000),
                patch.object(plugin.os, "getgid", create=True, return_value=1000),
            ):
                await ws.initialize()
                await ws.close()
            assert ["chown", "-R", "1000:1000", "/workspace"] in backend.shell
            assert ["mkdir", "-p", "/workspace"] in backend.shell

    asyncio.run(_run())


def test_initialize_is_idempotent() -> None:
    async def _run() -> None:
        _plugin, _df, _be, ws, fake = _workspace(workspace_id="once")
        assert fake is not None
        await ws.initialize()
        await ws.initialize()
        assert len(fake.containers.items) == 1

    asyncio.run(_run())


if __name__ == "__main__":
    test_plugin_identity()
    test_image_tag_is_stable_and_tracks_inputs()
    test_prepare_build_context_writes_dockerfile()
    test_backend_exec_read_write()
    test_backend_exec_timeout()
    test_ephemeral_container_config()
    test_persistent_bind_mount_and_cache_hit()
    test_build_failure_includes_log_tail()
    test_legacy_workdir_kwarg()
    test_linux_teardown_chowns_bind_mount()
    test_initialize_is_idempotent()
    print("workspace_test ok")
