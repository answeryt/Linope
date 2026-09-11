"""Shared real-provider helper assembled through the project's lip context."""

from __future__ import annotations

import asyncio
import gc
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[6]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Real assembly entrypoint (non-test scaffolding).
from capability.model.test import assemble

# Optional API key marker for callers that want to skip when env vars are missing.
API_KEY: str = os.getenv("OPENAI_API_KEY", "") if (os := __import__("os")) else ""


def _response_text(chunk: Any) -> str:
    output_text = getattr(chunk, "output_text", None)
    if isinstance(output_text, str) and output_text:
        return output_text

    choices = getattr(chunk, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content

    parts: list[str] = []
    for item in getattr(chunk, "output", None) or ():
        for content in getattr(item, "content", None) or ():
            text = getattr(content, "text", None)
            if isinstance(text, str):
                parts.append(text)
    if parts:
        return "".join(parts)

    if isinstance(chunk, Mapping):
        return str(dict(chunk))
    return str(chunk)


async def ask_live_model(prompt: str) -> str:
    """Call the configured real model through lip and return its text."""
    lip = assemble()
    chunks: list[Any] = []
    try:
        model = getattr(lip, "target", lip)
        stream = model.stream if callable(getattr(model, "stream", None)) else lip
        chunks = [
            item
            async for item in stream(
                {
                    "provider": "openai",
                    "messages": [{"role": "user", "content": prompt}],
                    "input_items": [{"role": "user", "content": prompt}],
                }
            )
        ]
        if not chunks:
            raise AssertionError("the live model returned no response")
        text = "".join(_response_text(chunk) for chunk in chunks)
    finally:
        lip.unload()
        chunks.clear()
        # The interface currently creates an AsyncClient per call without
        # exposing it. Collect while this test's event loop is still alive so
        # OpenAI's deferred client cleanup can finish before unittest closes it.
        gc.collect()
        await asyncio.sleep(0.25)
    return text