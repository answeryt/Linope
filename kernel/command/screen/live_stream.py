"""Show one text fragment with the event the terminal already understands."""

from __future__ import annotations

import json


def publish_text(text: str) -> None:
    """Print one piece of a model reply as a text-delta event."""
    print(
        json.dumps({"type": "text-delta", "text": text}, ensure_ascii=False),
        flush=True,
    )
