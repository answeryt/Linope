"""Process identity checks used when a ledger row outlives its OS process."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def process_identity(pid: int | None) -> str | None:
    alive, identity = _inspect(pid)
    return identity if alive else None


def process_matches(pid: int | None, identity: str | None) -> bool:
    alive, current = _inspect(pid)
    if not alive:
        return False
    if not identity or not current:
        return True
    return current == identity


def _inspect(pid: int | None) -> tuple[bool, str | None]:
    if pid is None or pid <= 0:
        return False, None
    if sys.platform == "win32":
        return _windows(pid)
    return _posix(pid)


def _posix(pid: int) -> tuple[bool, str | None]:
    try:
        os.kill(pid, 0)
    except OSError:
        return False, None
    stat = Path(f"/proc/{pid}/stat")
    if not stat.is_file():
        return True, None
    text = stat.read_text(encoding="utf-8", errors="replace")
    marker = text.rfind(")")
    if marker < 0:
        return True, None
    fields = text[marker + 2 :].split()
    if len(fields) < 20:
        return True, None
    return True, f"unix:{fields[19]}"


def _windows(pid: int) -> tuple[bool, str | None]:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    access = 0x1000
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        return False, None
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False, None
        if code.value != 259:
            return False, None

        class FILETIME(ctypes.Structure):
            _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]

        created = FILETIME()
        unused = FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(unused),
            ctypes.byref(unused),
            ctypes.byref(unused),
        ):
            return True, None
        stamp = (int(created.hi) << 32) | int(created.lo)
        return True, f"win:{stamp}"
    finally:
        kernel32.CloseHandle(handle)
