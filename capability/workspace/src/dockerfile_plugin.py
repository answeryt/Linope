# -*- coding: utf-8 -*-
"""Stdlib Docker build context for a workspace image.

The tag is a content hash of the Dockerfile plus every COPY payload so a
local tag hit can skip the daemon build. Host does not import this from
the workspace plugin; it injects ``prepare_build_context``.
"""

from __future__ import annotations

import hashlib
import shlex
import tempfile
from pathlib import Path


PLUGIN_NAME = "sandbox_workspace_dockerfile"
PLUGIN_VERSION = "1.0"

DEFAULT_BASE_IMAGE = "python:3.11-slim"
CONTAINER_WORKDIR = "/workspace"
IMAGE_REPO = "sandbox-workspace"


def render_dockerfile(
    *,
    base_image: str = DEFAULT_BASE_IMAGE,
    container_workdir: str = CONTAINER_WORKDIR,
    node_version: str | None = None,
    extra_pip: list[str] | None = None,
) -> str:
    """Render a Dockerfile that only needs python3 on PATH.

    AgentScope's image also baked an MCP gateway, uv, and agentscope itself.
    Those are Host/plugin concerns here, not image layers.
    """
    lines: list[str] = []
    if node_version:
        lines.append(f"FROM node:{node_version}-slim AS node_stage")
    lines.append(f"FROM {base_image}")
    if node_version:
        lines.extend(
            [
                "COPY --from=node_stage /usr/local/bin/node /usr/local/bin/node",
                "COPY --from=node_stage /usr/local/lib/node_modules /usr/local/lib/node_modules",
                "RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \\",
                " && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx",
            ]
        )
    lines.append(f"WORKDIR {container_workdir}")
    packages = [str(item) for item in (extra_pip or []) if str(item).strip()]
    if packages:
        quoted = " ".join(shlex.quote(item) for item in packages)
        lines.append(f"RUN python3 -m pip install --no-cache-dir {quoted}")
    return "\n".join(lines) + "\n"


def compute_image_tag(
    dockerfile_text: str,
    copy_files: dict[str, bytes] | None = None,
) -> str:
    files = dict(copy_files or {})
    digest = hashlib.sha256()
    digest.update(b"DOCKERFILE\x00")
    digest.update(dockerfile_text.encode("utf-8"))
    for name in sorted(files):
        digest.update(b"\x00FILE\x00")
        digest.update(name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(files[name])
    return f"{IMAGE_REPO}:{digest.hexdigest()[:12]}"


def prepare_build_context(
    *,
    base_image: str = DEFAULT_BASE_IMAGE,
    container_workdir: str = CONTAINER_WORKDIR,
    node_version: str | None = None,
    extra_pip: list[str] | None = None,
) -> tuple[Path, str, dict[str, bytes]]:
    """Write a temp context with a Dockerfile. Caller deletes ``ctx_dir``."""
    dockerfile_text = render_dockerfile(
        base_image=base_image,
        container_workdir=container_workdir,
        node_version=node_version,
        extra_pip=extra_pip,
    )
    copy_files: dict[str, bytes] = {}
    tag = compute_image_tag(dockerfile_text, copy_files)
    ctx_dir = Path(tempfile.mkdtemp(prefix="sb-ws-build-"))
    (ctx_dir / "Dockerfile").write_text(dockerfile_text, encoding="utf-8")
    return ctx_dir, tag, copy_files
