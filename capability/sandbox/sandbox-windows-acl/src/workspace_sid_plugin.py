# -*- coding: utf-8 -*-
"""Deterministic workspace write SID and per-temp write SID."""

from __future__ import annotations

import hashlib
import struct


PLUGIN_NAME = "sandbox_windows_acl_workspace_sid"
PLUGIN_VERSION = "1.0"

_MOD = (2**30) - 1


def _pair(digest: bytes) -> tuple[int, int]:
    first = (struct.unpack_from("<I", digest, 0)[0] % _MOD) + 1
    second = (struct.unpack_from("<I", digest, 4)[0] % _MOD) + 1
    return first, second


def workspace_write_sid(workspace_root: str) -> str:
    first, second = _pair(hashlib.sha256(workspace_root.encode("utf-8")).digest())
    return f"S-1-4-{first}-{second}"


def temp_write_sid(temp_dir: str) -> str:
    digest = hashlib.sha256(b"temp\0" + temp_dir.encode("utf-8")).digest()
    first, second = _pair(digest)
    return f"S-1-4-{first}-{second}-1"
