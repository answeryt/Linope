# -*- coding: utf-8 -*-
"""Standing workspace ACE plus revocable temp ACE. Host injects ffi and ACL ops."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "sandbox_windows_acl_grant"
PLUGIN_VERSION = "1.0"


class AclWriteGrant:
    """One write SID's grants. Standing paths survive dispose(); temp paths do not."""

    def __init__(
        self,
        write_sid: str,
        api: Any,
        sid_ptr: Any,
        *,
        grant_write: Callable[..., None],
        revoke_write: Callable[..., bool],
        ffi: Any,
    ) -> None:
        self.write_sid = write_sid
        self.api = api
        self.sid_ptr = sid_ptr
        self._grant_write = grant_write
        self._revoke_write = revoke_write
        self._ffi = ffi
        self._revocable: list[str] = []
        self._standing: list[str] = []

    @property
    def paths(self) -> list[str]:
        return [*self._standing, *self._revocable]

    def add(self, path: str, standing: bool = False) -> None:
        (self._standing if standing else self._revocable).append(path)
        self._grant_write(self.api, path, self.sid_ptr, self._ffi)

    def dispose(self) -> None:
        failures: list[BaseException] = []
        for path in self._revocable:
            try:
                self._revoke_write(self.api, path, self.sid_ptr, self._ffi)
            except Exception as error:
                failures.append(error)
        try:
            freed = self.api.local_free(self.sid_ptr)
            if not self._ffi.is_null_ptr(freed):
                self._ffi.throw_last_error(self.api, "LocalFree", "write SID")
        except Exception as error:
            failures.append(error)
        if failures:
            error = RuntimeError(
                f"AclWriteGrant dispose completed with {len(failures)} cleanup failure(s)"
            )
            error.exceptions = failures
            raise error


def create_grant(
    write_sid: str,
    *,
    ffi: Any,
    grant_write: Callable[..., None],
    revoke_write: Callable[..., bool],
    api: Any | None = None,
) -> AclWriteGrant:
    bindings = api if api is not None else ffi.win32_sync()
    sid_slot = ffi.alloc_ptr_slot()
    if bindings.convert_string_sid_to_sid_w(write_sid, sid_slot) == 0:
        ffi.throw_last_error(bindings, "ConvertStringSidToSidW", write_sid)
    sid_ptr = ffi.decode_ptr(sid_slot)
    if sid_ptr is None:
        ffi.throw_last_error(bindings, "ConvertStringSidToSidW", f"null SID for {write_sid}")
    return AclWriteGrant(
        write_sid,
        bindings,
        sid_ptr,
        grant_write=grant_write,
        revoke_write=revoke_write,
        ffi=ffi,
    )
