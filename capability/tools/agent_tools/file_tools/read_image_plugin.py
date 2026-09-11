# -*- coding: utf-8 -*-
"""Read a PNG/JPEG/WebP/GIF file and return image metadata for the model."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional


PLUGIN_NAME = "read_image"
PLUGIN_VERSION = "1.0"

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

READ_IMAGE_SCHEMA: dict[str, Any] = {
    "name": "read_image",
    "description": (
        "Read a PNG/JPEG/WebP/GIF file and return the image itself. "
        "Requires the current model to accept image input."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the image file, resolved by the filesystem backend.",
            },
        },
        "required": ["file_path"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [READ_IMAGE_SCHEMA]


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "read_image":
        return _error(f"unknown tool: {name}")
    return read_image(str(arguments.get("file_path") or ""), **kwargs)


def read_image(file_path: str, workspace: Optional[str] = None) -> str:
    path = _resolve(file_path, workspace)
    if not path.is_file():
        return _error(f"file not found: {path}")
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        return _error(f"unsupported image type: {path.suffix}")
    return json.dumps(
        {
            "success": True,
            "path": str(path),
            "mediaType": {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
            }.get(path.suffix.lower(), "application/octet-stream"),
            "bytes": path.stat().st_size,
        },
        ensure_ascii=False,
    )


def _resolve(file_path: str, workspace: Optional[str]) -> Path:
    root = Path(workspace or os.getenv("TERMINAL_CWD") or os.getcwd())
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve()


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)
