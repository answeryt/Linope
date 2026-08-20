# -*- coding: utf-8 -*-
"""Standalone MCP content-result renderer and bounded media cache."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import mimetypes
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


PLUGIN_NAME = "mcp_content_results"
PLUGIN_VERSION = "1.0"


class MCPContentError(ValueError):
    """Raised when an MCP content block is malformed or unsafe."""


class MCPContentPlugin:
    """Render text, media, resources, and structured MCP tool results."""

    def __init__(
        self,
        *,
        cache_dir: str | os.PathLike[str] | None = None,
        max_bytes: int = 50 * 1024 * 1024,
        media_prefix: str = "MEDIA:",
    ) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive.")
        self.cache_dir = Path(
            cache_dir
            if cache_dir is not None
            else Path(tempfile.gettempdir()) / "open-linux-mcp-content",
        )
        self.max_bytes = max_bytes
        self.max_base64_chars = max_bytes * 4 // 3 + 4
        self.media_prefix = media_prefix

    @staticmethod
    def _mime(mime_type: Any) -> str:
        return str(mime_type or "").split(";", 1)[0].strip().lower()

    @staticmethod
    def _clean_marker_value(value: Any, limit: int = 500) -> str:
        text = re.sub(r"[\x00-\x1f\x7f]", "", str(value or ""))
        return text[:limit]

    @staticmethod
    def _safe_filename(uri: Any, mime_type: str) -> str:
        name = ""
        try:
            name = Path(unquote(urlparse(str(uri or "")).path)).name
        except (TypeError, ValueError):
            pass
        name = re.sub(r"[\x00-\x1f\x7f<>:\"/\\|?*]", "_", name).strip(" .")
        if len(name) > 150:
            stem, suffix = os.path.splitext(name)
            name = stem[: 150 - len(suffix)] + suffix[:13]
        if not name or name in {".", ".."}:
            extension = mimetypes.guess_extension(mime_type) or ".bin"
            name = f"resource{extension}"
        return name

    def _decode(self, data: Any, label: str) -> bytes:
        if not isinstance(data, (str, bytes)):
            raise MCPContentError(f"{label} payload must be base64 text.")
        if len(data) > self.max_base64_chars:
            raise MCPContentError(f"{label} exceeds the configured size limit.")
        try:
            raw = base64.b64decode(data, validate=True)
        except (binascii.Error, TypeError, ValueError) as error:
            raise MCPContentError(f"{label} contains invalid base64.") from error
        if len(raw) > self.max_bytes:
            raise MCPContentError(f"{label} exceeds the configured size limit.")
        return raw

    def _cache(self, raw: bytes, filename: str) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(raw).hexdigest()[:20]
        safe_name = self._safe_filename(filename, "")
        path = self.cache_dir / f"{digest}-{safe_name}"
        if not path.exists():
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(raw)
            temporary.replace(path)
        return path.resolve()

    def render_image(self, block: Any) -> str:
        """Cache one ImageContent block and return a host media marker."""
        mime = self._mime(getattr(block, "mimeType", None))
        if not mime.startswith("image/"):
            return ""
        raw = self._decode(getattr(block, "data", None), "MCP image")
        extension = ".jpg" if mime in {"image/jpeg", "image/jpg"} else (
            mimetypes.guess_extension(mime) or ".png"
        )
        path = self._cache(raw, f"image{extension}")
        return f"{self.media_prefix}{path}"

    def render_audio(self, block: Any) -> str:
        """Cache one AudioContent block and return a host media marker."""
        mime = self._mime(getattr(block, "mimeType", None))
        if not mime.startswith("audio/"):
            return ""
        raw = self._decode(getattr(block, "data", None), "MCP audio")
        extension = {
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/wave": ".wav",
        }.get(mime) or mimetypes.guess_extension(mime) or ".ogg"
        path = self._cache(raw, f"audio{extension}")
        return f"{self.media_prefix}{path}"

    def render_resource(self, block: Any, server_name: str = "") -> str:
        """Render ResourceLink or EmbeddedResource content."""
        block_type = str(getattr(block, "type", "") or "")
        resource = getattr(block, "resource", None)
        if resource is None and (
            block_type == "resource_link"
            or (hasattr(block, "uri") and not hasattr(block, "text"))
        ):
            uri = getattr(block, "uri", None)
            if uri is None:
                return ""
            details = [f"uri={self._clean_marker_value(uri)}"]
            for attribute in ("name", "mimeType"):
                value = getattr(block, attribute, None)
                if value:
                    details.append(
                        f"{attribute}={self._clean_marker_value(value)}",
                    )
            safe_server = re.sub(r"[^A-Za-z0-9_]", "_", server_name)
            reader = (
                f"mcp__{safe_server}__read_resource"
                if server_name
                else "read_resource"
            )
            return f"[MCP resource link: {', '.join(details)}; use {reader}]"
        if resource is None:
            return ""

        text = getattr(resource, "text", None)
        if text is not None:
            return str(text)
        blob = getattr(resource, "blob", None)
        if blob is None:
            return ""
        mime = self._mime(getattr(resource, "mimeType", None))
        uri = getattr(resource, "uri", "")
        raw = self._decode(blob, "MCP embedded resource")
        path = self._cache(raw, self._safe_filename(uri, mime))
        return (
            f"[MCP resource saved to {path} "
            f"({mime or 'unknown type'}, {len(raw)} bytes)]"
        )

    def render_block(self, block: Any, server_name: str = "") -> str:
        """Render one MCP content block without dropping recognized data."""
        text = getattr(block, "text", None)
        if text is not None:
            return str(text)
        mime = self._mime(getattr(block, "mimeType", None))
        try:
            if mime.startswith("image/"):
                return self.render_image(block)
            if mime.startswith("audio/"):
                return self.render_audio(block)
            return self.render_resource(block, server_name)
        except MCPContentError as error:
            return f"[{error}]"

    def render_tool_result(
        self,
        result: Any,
        *,
        server_name: str = "",
    ) -> dict[str, Any]:
        """Convert CallToolResult to a JSON-serializable host result."""
        parts = [
            rendered
            for block in (getattr(result, "content", None) or [])
            if (rendered := self.render_block(block, server_name))
        ]
        text = "\n".join(parts)
        structured = getattr(result, "structuredContent", None)
        if bool(getattr(result, "isError", False)):
            output: dict[str, Any] = {
                "error": text or "MCP tool returned an error",
            }
            if structured is not None:
                output["structuredContent"] = structured
            return output

        output: dict[str, Any] = {"result": text}
        if structured is not None:
            output["structuredContent"] = structured
            if not text:
                output["result"] = structured
        return output

    def render_read_resource(self, result: Any) -> dict[str, Any]:
        """Render a ReadResourceResult including binary contents."""
        parts: list[str] = []
        for content in getattr(result, "contents", None) or []:
            text = getattr(content, "text", None)
            if text is not None:
                parts.append(str(text))
                continue
            blob = getattr(content, "blob", None)
            if blob is not None:
                wrapper = type("_EmbeddedResource", (), {})()
                wrapper.type = "resource"
                wrapper.resource = content
                parts.append(self.render_resource(wrapper))
        return {"result": "\n".join(parts)}

    def dumps_tool_result(self, result: Any, *, server_name: str = "") -> str:
        """Return a serialized host result suitable for tool dispatch."""
        return json.dumps(
            self.render_tool_result(result, server_name=server_name),
            ensure_ascii=False,
            default=str,
        )
