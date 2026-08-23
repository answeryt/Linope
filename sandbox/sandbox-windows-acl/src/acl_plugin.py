# -*- coding: utf-8 -*-
"""Grant or revoke a capability SID on a directory DACL. Host injects ffi."""

from __future__ import annotations

import hashlib
import os
import struct
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "sandbox_windows_acl_acl"
PLUGIN_VERSION = "1.0"

EXPLICIT_ACCESS_W_SIZE = 48
SUB_CONTAINERS_AND_OBJECTS_INHERIT = 0x3
NO_MULTIPLE_TRUSTEE = 0
TRUSTEE_IS_SID = 0
TRUSTEE_IS_UNKNOWN = 0
GRANT_ACCESS = 1
REVOKE_ACCESS = 4
GRANT_MASK = 0x00110156
SE_FILE_OBJECT = 1
DACL_SECURITY_INFORMATION = 4
ERROR_SUCCESS = 0
ACCESS_ALLOWED_ACE_TYPE = 0
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_ALWAYS = 4
LOCKFILE_EXCLUSIVE_LOCK = 0x2


def build_explicit_access(sid_ptr: Any, mode: int, permissions: int, *, ptr_address: Callable[[Any], int]) -> bytes:
    entry = bytearray(EXPLICIT_ACCESS_W_SIZE)
    struct.pack_into("<I", entry, 0, permissions)
    struct.pack_into("<I", entry, 4, mode)
    struct.pack_into("<I", entry, 8, SUB_CONTAINERS_AND_OBJECTS_INHERIT)
    struct.pack_into("<I", entry, 24, NO_MULTIPLE_TRUSTEE)
    struct.pack_into("<I", entry, 28, TRUSTEE_IS_SID)
    struct.pack_into("<I", entry, 32, TRUSTEE_IS_UNKNOWN)
    struct.pack_into("<Q", entry, 40, ptr_address(sid_ptr))
    return bytes(entry)


def lock_file_path(api: Any, path: str, *, get_temp_path: Callable[[Any], str]) -> str:
    digest = hashlib.sha256(path.lower().encode("utf-8")).hexdigest()[:16]
    return os.path.join(get_temp_path(api), "ol-acl-locks", f"{digest}.lock")


def with_path_lock(api: Any, path: str, action: Callable[[], Any], ffi: Any) -> Any:
    lock_path = lock_file_path(api, path, get_temp_path=ffi.get_temp_path)
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    handle = api.create_file_w(
        lock_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_ALWAYS,
        0,
        None,
    )
    if ffi.is_invalid_handle(handle):
        ffi.throw_last_error(api, "CreateFileW", lock_path)
    overlapped = ffi.alloc_overlapped()
    if api.lock_file_ex(handle, LOCKFILE_EXCLUSIVE_LOCK, 0, 1, 0, overlapped) == 0:
        code = api.get_last_error()
        api.close_handle(handle)
        ffi.throw_win32(api, "LockFileEx", code, lock_path)
    try:
        result = action()
    except Exception:
        api.unlock_file_ex(handle, 0, 1, 0, overlapped)
        api.close_handle(handle)
        raise
    if api.unlock_file_ex(handle, 0, 1, 0, overlapped) == 0:
        code = api.get_last_error()
        api.close_handle(handle)
        ffi.throw_win32(api, "UnlockFileEx", code, lock_path)
    if api.close_handle(handle) == 0:
        ffi.throw_last_error(api, "CloseHandle", f"lock file {lock_path}")
    return result


def _read_current_dacl(api: Any, path: str, ffi: Any) -> tuple[Any, Any]:
    owner = ffi.alloc_ptr_slot()
    group = ffi.alloc_ptr_slot()
    dacl = ffi.alloc_ptr_slot()
    sacl = ffi.alloc_ptr_slot()
    descriptor = ffi.alloc_ptr_slot()
    result = api.get_named_security_info_w(
        path, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION, owner, group, dacl, sacl, descriptor
    )
    if result != ERROR_SUCCESS:
        ffi.throw_win32(api, "GetNamedSecurityInfoW", result, path)
    return ffi.decode_ptr(dacl), ffi.decode_ptr(descriptor)


def _merge_and_apply(api: Any, path: str, entry: bytes, old_acl: Any, descriptor: Any, label: str, ffi: Any) -> None:
    new_acl_slot = ffi.alloc_ptr_slot()
    merge = api.set_entries_in_acl_w(1, entry, old_acl, new_acl_slot)
    if merge != ERROR_SUCCESS:
        if descriptor is not None:
            api.local_free(descriptor)
        ffi.throw_win32(api, "SetEntriesInAclW", merge, f"{label}({path})")
    new_acl = ffi.decode_ptr(new_acl_slot)
    if new_acl is None:
        if descriptor is not None:
            api.local_free(descriptor)
        ffi.throw_win32(api, "SetEntriesInAclW", api.get_last_error(), f"{label}({path}): null new ACL")
    freed_descriptor = api.local_free(descriptor) if descriptor is not None else None
    apply_result = api.set_named_security_info_w(
        path, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION, None, None, new_acl, None
    )
    freed_new = api.local_free(new_acl)
    if apply_result != ERROR_SUCCESS:
        ffi.throw_win32(api, "SetNamedSecurityInfoW", apply_result, f"{label}({path})")
    if freed_descriptor is not None and not ffi.is_null_ptr(freed_descriptor):
        ffi.throw_last_error(api, "LocalFree", f"{label}({path}) descriptor")
    if not ffi.is_null_ptr(freed_new):
        ffi.throw_last_error(api, "LocalFree", f"{label}({path}) new ACL")


def _has_exact_grant(old_acl: Any, sid_ptr: Any, ffi: Any) -> bool:
    acl_size = ffi.decode_uint16_at(old_acl, 2)
    ace_count = ffi.decode_uint16_at(old_acl, 4)
    if acl_size < 8 or acl_size > 1_048_576:
        return False
    offset = 8
    for _ in range(ace_count):
        ace_size = ffi.decode_uint16_at(old_acl, offset + 2)
        if ace_size < 8 or offset + ace_size > acl_size:
            return False
        exact = (
            ffi.decode_uint8_at(old_acl, offset) == ACCESS_ALLOWED_ACE_TYPE
            and ffi.decode_uint8_at(old_acl, offset + 1) == SUB_CONTAINERS_AND_OBJECTS_INHERIT
            and ffi.decode_uint32_at(old_acl, offset + 4) == GRANT_MASK
        )
        if exact and ffi.same_sid_at(old_acl, offset + 8, sid_ptr, 0):
            return True
        offset += ace_size
    return False


def grant_write(api: Any, path: str, sid_ptr: Any, ffi: Any) -> None:
    def _apply() -> None:
        old_acl, descriptor = _read_current_dacl(api, path, ffi)
        if old_acl is not None and _has_exact_grant(old_acl, sid_ptr, ffi):
            if descriptor is not None:
                freed = api.local_free(descriptor)
                if not ffi.is_null_ptr(freed):
                    ffi.throw_last_error(api, "LocalFree", f"grantWrite({path}) descriptor")
            return
        _merge_and_apply(
            api,
            path,
            build_explicit_access(sid_ptr, GRANT_ACCESS, GRANT_MASK, ptr_address=ffi.ptr_address),
            old_acl,
            descriptor,
            "grantWrite",
            ffi,
        )

    with_path_lock(api, path, _apply, ffi)


def revoke_write(api: Any, path: str, sid_ptr: Any, ffi: Any) -> bool:
    def _apply() -> bool:
        old_acl, descriptor = _read_current_dacl(api, path, ffi)
        if old_acl is None:
            if descriptor is not None:
                freed = api.local_free(descriptor)
                if not ffi.is_null_ptr(freed):
                    ffi.throw_last_error(api, "LocalFree", f"revokeWrite({path}) descriptor")
            return False
        _merge_and_apply(
            api,
            path,
            build_explicit_access(sid_ptr, REVOKE_ACCESS, 0, ptr_address=ffi.ptr_address),
            old_acl,
            descriptor,
            "revokeWrite",
            ffi,
        )
        return True

    return with_path_lock(api, path, _apply, ffi)
