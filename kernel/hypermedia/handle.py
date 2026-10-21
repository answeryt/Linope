"""Opaque link handles. Knowing a pid or an address is not the right to follow it."""

from __future__ import annotations

import hashlib
import hmac
import secrets

_KEY = secrets.token_bytes(32)


def opaque(*parts: object) -> str:
    """One hex handle for these parts. It changes when any part, such as the seq, changes."""
    text = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hmac.new(_KEY, text, hashlib.sha256).hexdigest()[:32]
