# -*- coding: utf-8 -*-
"""Fail-closed Win32 error. Every API failure raises this; never spawn unrestricted."""

from __future__ import annotations


PLUGIN_NAME = "sandbox_windows_acl_errors"
PLUGIN_VERSION = "1.0"


class Win32Error(Exception):
    """A checked Win32 failure: API name plus the exact error code."""

    def __init__(self, api: str, win32_code: int, detail: str | None = None) -> None:
        extra = "" if detail is None else f": {detail}"
        super().__init__(f"{api} failed (Win32 {win32_code}){extra}")
        self.name = "Win32Error"
        self.api = api
        self.win32_code = win32_code
