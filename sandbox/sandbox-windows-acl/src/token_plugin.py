# -*- coding: utf-8 -*-
"""WRITE_RESTRICTED token construction. Host injects ffi and build_explicit_access."""

from __future__ import annotations

import os
import struct
from collections.abc import Callable, Sequence
from typing import Any


PLUGIN_NAME = "sandbox_windows_acl_token"
PLUGIN_VERSION = "1.0"

PROCESS_QUERY_INFORMATION = 0x0400
TOKEN_QUERY = 0x0008
TOKEN_DUPLICATE = 0x0002
TOKEN_ADJUST_DEFAULT = 0x0080
TOKEN_ASSIGN_PRIMARY = 0x0001
TOKEN_GROUPS = 2
TOKEN_DEFAULT_DACL = 6
TOKEN_GROUPS_OFFSET = 8
SID_AND_ATTRIBUTES_SIZE = 16
SE_GROUP_LOGON_ID = 0xC0000000
SECURITY_MAX_SID_SIZE = 68
WIN_WORLD_SID = 1
DISABLE_MAX_PRIVILEGE = 0x1
LUA_TOKEN = 0x4
WRITE_RESTRICTED = 0x8
ERROR_SUCCESS = 0
GRANT_ACCESS = 1
FILE_ALL_ACCESS = 0x1F01FF
READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"


def open_current_process_token(api: Any, ffi: Any) -> int:
    process_handle = api.open_process(PROCESS_QUERY_INFORMATION, 0, os.getpid())
    if ffi.is_null_ptr(process_handle):
        ffi.throw_last_error(api, "OpenProcess", f"pid {os.getpid()}")
    token_slot = ffi.alloc_ptr_slot()
    opened = api.open_process_token(
        process_handle,
        TOKEN_QUERY | TOKEN_DUPLICATE | TOKEN_ADJUST_DEFAULT | TOKEN_ASSIGN_PRIMARY,
        token_slot,
    )
    if opened == 0:
        code = api.get_last_error()
        api.close_handle(process_handle)
        ffi.throw_win32(api, "OpenProcessToken", code, f"pid {os.getpid()}")
    if api.close_handle(process_handle) == 0:
        ffi.throw_last_error(api, "CloseHandle", "OpenProcess process handle")
    token = ffi.decode_ptr(token_slot)
    if token is None:
        ffi.throw_win32(api, "OpenProcessToken", api.get_last_error(), "null token handle")
    return token


def find_logon_sid(api: Any, token: Any, ffi: Any) -> int:
    needed = ffi.alloc_uint32()
    api.get_token_information(token, TOKEN_GROUPS, None, 0, needed)
    size = ffi.decode_uint32(needed)
    if size == 0:
        ffi.throw_last_error(api, "GetTokenInformation", "TokenGroups size query")
    if size < TOKEN_GROUPS_OFFSET:
        ffi.throw_win32(api, "GetTokenInformation", api.get_last_error(), f"implausible TokenGroups size {size}")
    groups = ctypes_buffer(size)
    if api.get_token_information(token, TOKEN_GROUPS, groups, size, needed) == 0:
        ffi.throw_last_error(api, "GetTokenInformation", "TokenGroups")
    raw = bytes(groups)
    group_count = struct.unpack_from("<I", raw, 0)[0]
    for index in range(group_count):
        base = TOKEN_GROUPS_OFFSET + index * SID_AND_ATTRIBUTES_SIZE
        sid_ptr = ffi.decode_ptr_at(raw, base)
        attributes = struct.unpack_from("<I", raw, base + 8)[0]
        is_logon = (attributes & SE_GROUP_LOGON_ID) & 0xFFFFFFFF == SE_GROUP_LOGON_ID & 0xFFFFFFFF
        if sid_ptr is None or not is_logon:
            continue
        sid_length = api.get_length_sid(sid_ptr)
        if sid_length == 0:
            ffi.throw_last_error(api, "GetLengthSid", f"logon SID group {index}")
        copy = ffi.alloc_bytes(api, sid_length)
        if api.copy_sid(sid_length, copy, sid_ptr) == 0:
            ffi.throw_last_error(api, "CopySid", f"logon SID group {index}")
        return copy
    raise RuntimeError(
        f"CreateRestrictedToken prerequisite failed: no logon SID found among {group_count} token groups"
    )


def make_well_known_sid(api: Any, sid_type: int, ffi: Any) -> int:
    sid = ffi.alloc_bytes(api, SECURITY_MAX_SID_SIZE)
    size = ffi.alloc_uint32()
    ffi.encode_uint32(size, SECURITY_MAX_SID_SIZE)
    if api.create_well_known_sid(sid_type, None, sid, size) == 0:
        ffi.throw_last_error(api, "CreateWellKnownSid", f"type {sid_type}")
    if api.is_valid_sid(sid) == 0:
        ffi.throw_last_error(api, "IsValidSid", f"CreateWellKnownSid type {sid_type}")
    return sid


def set_token_default_dacl_grant(
    api: Any,
    token: Any,
    sid_ptr: Any,
    ffi: Any,
    *,
    build_explicit_access: Callable[..., bytes],
) -> None:
    needed = ffi.alloc_uint32()
    api.get_token_information(token, TOKEN_DEFAULT_DACL, None, 0, needed)
    size = ffi.decode_uint32(needed)
    if size == 0:
        ffi.throw_last_error(api, "GetTokenInformation", "TokenDefaultDacl size query")
    buffer = ctypes_buffer(size)
    if api.get_token_information(token, TOKEN_DEFAULT_DACL, buffer, size, needed) == 0:
        ffi.throw_last_error(api, "GetTokenInformation", "TokenDefaultDacl")
    current = ffi.decode_ptr_at(bytes(buffer), 0)
    if current is None:
        raise RuntimeError("setTokenDefaultDaclGrant: the token carries no default DACL to extend")
    new_dacl_slot = ffi.alloc_ptr_slot()
    entry = build_explicit_access(sid_ptr, GRANT_ACCESS, FILE_ALL_ACCESS, ptr_address=ffi.ptr_address)
    result = api.set_entries_in_acl_w(1, entry, current, new_dacl_slot)
    if result != ERROR_SUCCESS:
        ffi.throw_win32(api, "SetEntriesInAclW", result, "default DACL merge")
    new_dacl = ffi.decode_ptr(new_dacl_slot)
    if new_dacl is None:
        ffi.throw_win32(api, "SetEntriesInAclW", result, "null merged default DACL")
    info = bytearray(8)
    struct.pack_into("<Q", info, 0, ffi.ptr_address(new_dacl))
    if api.set_token_information(token, TOKEN_DEFAULT_DACL, bytes(info), len(info)) == 0:
        code = api.get_last_error()
        api.local_free(new_dacl)
        ffi.throw_win32(api, "SetTokenInformation", code, "TokenDefaultDacl")
    api.local_free(new_dacl)


def create_restricted_token(
    api: Any,
    current_token: Any,
    logon_sid: Any,
    write_sids: Sequence[Any],
    known: dict[str, Any],
    mode: str,
    ffi: Any,
) -> int:
    if mode == READ_ONLY:
        sids = [logon_sid, known["world"]]
    elif not write_sids:
        raise RuntimeError("createRestrictedToken: workspace-write restricting list requires at least one write SID")
    else:
        sids = [logon_sid, known["world"], *write_sids]
    packed = bytearray(SID_AND_ATTRIBUTES_SIZE * len(sids))
    for index, sid in enumerate(sids):
        struct.pack_into("<Q", packed, SID_AND_ATTRIBUTES_SIZE * index, ffi.ptr_address(sid))
    token_slot = ffi.alloc_ptr_slot()
    created = api.create_restricted_token(
        current_token,
        DISABLE_MAX_PRIVILEGE | LUA_TOKEN | WRITE_RESTRICTED,
        0,
        None,
        0,
        None,
        len(sids),
        bytes(packed),
        token_slot,
    )
    if created == 0:
        ffi.throw_last_error(api, "CreateRestrictedToken", f"restricting SIDs: {len(sids)}")
    token = ffi.decode_ptr(token_slot)
    if token is None:
        ffi.throw_win32(api, "CreateRestrictedToken", api.get_last_error(), "null token handle")
    return token


def ctypes_buffer(size: int) -> Any:
    import ctypes

    return (ctypes.c_ubyte * size)()
