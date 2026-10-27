# -*- coding: utf-8 -*-
"""Lazy ctypes bindings for the Windows ACL sandbox. Non-Windows never loads DLLs."""

from __future__ import annotations

import ctypes
import struct
import sys
from ctypes import wintypes
from typing import Any


PLUGIN_NAME = "sandbox_windows_acl_ffi"
PLUGIN_VERSION = "1.0"

FORMAT_MESSAGE_FROM_SYSTEM = 0x00001000
FORMAT_MESSAGE_IGNORE_INSERTS = 0x00000200
ERROR_INSUFFICIENT_BUFFER = 122
MAX_PATH = 260
SID_MAX_SUB_AUTHORITIES = 15
STARTUPINFOW_SIZE = 104
PROCESS_INFORMATION_SIZE = 24
LMEM_ZEROINIT = 0x0040
INVALID_HANDLE = 0xFFFFFFFFFFFFFFFF


class Win32Error(Exception):
    def __init__(self, api: str, win32_code: int, detail: str | None = None) -> None:
        extra = "" if detail is None else f": {detail}"
        super().__init__(f"{api} failed (Win32 {win32_code}){extra}")
        self.name = "Win32Error"
        self.api = api
        self.win32_code = win32_code


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class OVERLAPPED(ctypes.Structure):
    _fields_ = [
        ("Internal", ctypes.c_ulonglong),
        ("InternalHigh", ctypes.c_ulonglong),
        ("Offset", wintypes.DWORD),
        ("OffsetHigh", wintypes.DWORD),
        ("hEvent", wintypes.HANDLE),
    ]


def is_null_ptr(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, ctypes.c_void_p):
        return not value.value
    return int(value) == 0


def is_invalid_handle(handle: Any) -> bool:
    if is_null_ptr(handle):
        return True
    address = _addr(handle)
    return address in {INVALID_HANDLE, -1}


def _addr(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, ctypes.c_void_p):
        return int(value.value or 0)
    if hasattr(value, "value") and not isinstance(value, int):
        raw = value.value
        return 0 if raw is None else int(raw)
    return int(value)


def alloc_ptr_slot() -> ctypes.c_void_p:
    return ctypes.c_void_p()


def alloc_uint32() -> ctypes.c_uint32:
    return ctypes.c_uint32()


def encode_uint32(slot: ctypes.c_uint32, value: int) -> None:
    slot.value = value


def decode_ptr(slot: ctypes.c_void_p) -> int | None:
    if not slot.value:
        return None
    return int(slot.value)


def decode_uint32(slot: ctypes.c_uint32) -> int:
    return int(slot.value)


def ptr_address(ptr: Any) -> int:
    return _addr(ptr)


def decode_ptr_at(buffer: bytes | bytearray | memoryview, offset: int) -> int | None:
    address = struct.unpack_from("<Q", buffer, offset)[0]
    return None if address == 0 else int(address)


def decode_uint8_at(ptr: Any, offset: int) -> int:
    return ctypes.string_at(_addr(ptr) + offset, 1)[0]


def decode_uint16_at(ptr: Any, offset: int) -> int:
    return struct.unpack("<H", ctypes.string_at(_addr(ptr) + offset, 2))[0]


def decode_uint32_at(ptr: Any, offset: int) -> int:
    return struct.unpack("<I", ctypes.string_at(_addr(ptr) + offset, 4))[0]


def same_sid_at(left: Any, left_offset: int, right: Any, right_offset: int) -> bool:
    if decode_uint8_at(left, left_offset) != decode_uint8_at(right, right_offset):
        return False
    left_count = decode_uint8_at(left, left_offset + 1)
    right_count = decode_uint8_at(right, right_offset + 1)
    if left_count != right_count or left_count > SID_MAX_SUB_AUTHORITIES:
        return False
    for index in range(6):
        if decode_uint8_at(left, left_offset + 2 + index) != decode_uint8_at(
            right, right_offset + 2 + index
        ):
            return False
    for index in range(left_count):
        if decode_uint32_at(left, left_offset + 8 + index * 4) != decode_uint32_at(
            right, right_offset + 8 + index * 4
        ):
            return False
    return True


def alloc_startup_info() -> STARTUPINFOW:
    info = STARTUPINFOW()
    info.cb = STARTUPINFOW_SIZE
    return info


def encode_startup_info(startup: STARTUPINFOW, fields: dict[str, Any]) -> None:
    startup.cb = int(fields.get("cb", STARTUPINFOW_SIZE))
    startup.dwFlags = int(fields.get("dwFlags", 0))
    startup.hStdInput = fields.get("hStdInput")
    startup.hStdOutput = fields.get("hStdOutput")
    startup.hStdError = fields.get("hStdError")


def alloc_process_info() -> PROCESS_INFORMATION:
    return PROCESS_INFORMATION()


def decode_process_info(info: PROCESS_INFORMATION) -> dict[str, Any]:
    return {
        "hProcess": None if is_null_ptr(info.hProcess) else _addr(info.hProcess),
        "hThread": None if is_null_ptr(info.hThread) else _addr(info.hThread),
        "dwProcessId": int(info.dwProcessId),
        "dwThreadId": int(info.dwThreadId),
    }


def alloc_overlapped() -> OVERLAPPED:
    return OVERLAPPED()


class Win32Bindings:
    """Checked kernel32/advapi32 table. Loaded only on win32."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("Windows ACL bindings require win32")
        if ctypes.sizeof(STARTUPINFOW) != STARTUPINFOW_SIZE:
            raise RuntimeError(
                f"STARTUPINFOW layout mismatch: {ctypes.sizeof(STARTUPINFOW)} vs {STARTUPINFOW_SIZE}"
            )
        if ctypes.sizeof(PROCESS_INFORMATION) != PROCESS_INFORMATION_SIZE:
            raise RuntimeError(
                f"PROCESS_INFORMATION layout mismatch: {ctypes.sizeof(PROCESS_INFORMATION)} "
                f"vs {PROCESS_INFORMATION_SIZE}"
            )
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self._kernel32 = kernel32
        self._advapi32 = advapi32
        self.get_last_error = ctypes.get_last_error
        self._bind(kernel32, advapi32)

    def _bind(self, kernel32: Any, advapi32: Any) -> None:
        self._OpenProcess = kernel32.OpenProcess
        self._OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._OpenProcess.restype = wintypes.HANDLE
        self._OpenProcessToken = advapi32.OpenProcessToken
        self._OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        self._OpenProcessToken.restype = wintypes.BOOL
        self._CloseHandle = kernel32.CloseHandle
        self._CloseHandle.argtypes = [wintypes.HANDLE]
        self._CloseHandle.restype = wintypes.BOOL
        self._FormatMessageW = kernel32.FormatMessageW
        self._LocalAlloc = kernel32.LocalAlloc
        self._LocalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        self._LocalAlloc.restype = ctypes.c_void_p
        self._LocalFree = kernel32.LocalFree
        self._LocalFree.argtypes = [ctypes.c_void_p]
        self._LocalFree.restype = ctypes.c_void_p
        self._ConvertStringSidToSidW = advapi32.ConvertStringSidToSidW
        self._CreateWellKnownSid = advapi32.CreateWellKnownSid
        self._IsValidSid = advapi32.IsValidSid
        self._GetLengthSid = advapi32.GetLengthSid
        self._GetLengthSid.argtypes = [ctypes.c_void_p]
        self._GetLengthSid.restype = wintypes.DWORD
        self._CopySid = advapi32.CopySid
        self._CopySid.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
        self._CopySid.restype = wintypes.BOOL
        self._IsValidSid.argtypes = [ctypes.c_void_p]
        self._IsValidSid.restype = wintypes.BOOL
        self._CreateWellKnownSid.argtypes = [
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._CreateWellKnownSid.restype = wintypes.BOOL
        self._GetTokenInformation = advapi32.GetTokenInformation
        self._GetTokenInformation.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._GetTokenInformation.restype = wintypes.BOOL
        self._SetTokenInformation = advapi32.SetTokenInformation
        self._SetTokenInformation.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_char_p,
            wintypes.DWORD,
        ]
        self._SetTokenInformation.restype = wintypes.BOOL
        self._CreateRestrictedToken = advapi32.CreateRestrictedToken
        self._CreateRestrictedToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_char_p,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        self._CreateRestrictedToken.restype = wintypes.BOOL
        self._SetEntriesInAclW = advapi32.SetEntriesInAclW
        self._SetEntriesInAclW.argtypes = [
            wintypes.ULONG,
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._SetEntriesInAclW.restype = wintypes.DWORD
        self._SetNamedSecurityInfoW = advapi32.SetNamedSecurityInfoW
        self._GetNamedSecurityInfoW = advapi32.GetNamedSecurityInfoW
        self._GetTempPathW = kernel32.GetTempPathW
        self._CreateFileW = kernel32.CreateFileW
        self._LockFileEx = kernel32.LockFileEx
        self._UnlockFileEx = kernel32.UnlockFileEx
        self._CreatePipe = kernel32.CreatePipe
        self._SetHandleInformation = kernel32.SetHandleInformation
        self._SetHandleInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
        self._SetHandleInformation.restype = wintypes.BOOL
        self._CreateProcessAsUserW = advapi32.CreateProcessAsUserW
        self._SetEnvironmentVariableW = kernel32.SetEnvironmentVariableW
        self._ReadFile = kernel32.ReadFile
        self._PeekNamedPipe = kernel32.PeekNamedPipe
        self._WaitForSingleObject = kernel32.WaitForSingleObject
        self._GetExitCodeProcess = kernel32.GetExitCodeProcess
        self._ResumeThread = kernel32.ResumeThread
        self._CreateJobObjectW = kernel32.CreateJobObjectW
        self._SetInformationJobObject = kernel32.SetInformationJobObject
        self._AssignProcessToJobObject = kernel32.AssignProcessToJobObject
        self._TerminateProcess = kernel32.TerminateProcess
        self._SetConsoleCtrlHandler = kernel32.SetConsoleCtrlHandler
        self._GetStdHandle = kernel32.GetStdHandle
        self._GetStdHandle.restype = wintypes.HANDLE

    def open_process(self, desired_access: int, inherit: int, pid: int) -> int | None:
        handle = self._OpenProcess(desired_access, inherit, pid)
        return None if is_null_ptr(handle) else _addr(handle)

    def open_process_token(self, process: Any, desired_access: int, token_slot: ctypes.c_void_p) -> int:
        handle = wintypes.HANDLE()
        ok = self._OpenProcessToken(process, desired_access, ctypes.byref(handle))
        token_slot.value = _addr(handle)
        return int(ok)

    def close_handle(self, handle: Any) -> int:
        return int(self._CloseHandle(handle))

    def format_message_w(self, flags: int, _source: None, message_id: int, language_id: int, buffer: Any, size: int, _args: None) -> int:
        return int(self._FormatMessageW(flags, None, message_id, language_id, buffer, size, None))

    def local_alloc(self, flags: int, nbytes: int) -> int | None:
        ptr = self._LocalAlloc(flags, nbytes)
        return None if not ptr else int(ptr)

    def local_free(self, memory: Any) -> int | None:
        freed = self._LocalFree(memory)
        return None if not freed else int(freed)

    def convert_string_sid_to_sid_w(self, string_sid: str, sid_slot: ctypes.c_void_p) -> int:
        return int(self._ConvertStringSidToSidW(string_sid, ctypes.byref(sid_slot)))

    def create_well_known_sid(self, sid_type: int, _domain: None, sid: Any, size_slot: ctypes.c_uint32) -> int:
        return int(self._CreateWellKnownSid(sid_type, None, sid, ctypes.byref(size_slot)))

    def is_valid_sid(self, sid: Any) -> int:
        return int(self._IsValidSid(sid))

    def get_length_sid(self, sid: Any) -> int:
        return int(self._GetLengthSid(sid))

    def copy_sid(self, length: int, destination: Any, source: Any) -> int:
        return int(self._CopySid(length, destination, source))

    def get_token_information(self, token: Any, cls: int, info: Any, length: int, needed: ctypes.c_uint32) -> int:
        return int(self._GetTokenInformation(token, cls, info, length, ctypes.byref(needed)))

    def set_token_information(self, token: Any, cls: int, info: Any, length: int) -> int:
        return int(self._SetTokenInformation(token, cls, info, length))

    def create_restricted_token(
        self,
        existing: Any,
        flags: int,
        disable_count: int,
        _disable_sids: None,
        delete_count: int,
        _privileges: None,
        restrict_count: int,
        restricting_sids: Any,
        new_token: ctypes.c_void_p,
    ) -> int:
        handle = wintypes.HANDLE()
        ok = self._CreateRestrictedToken(
            existing,
            flags,
            disable_count,
            None,
            delete_count,
            None,
            restrict_count,
            restricting_sids,
            ctypes.byref(handle),
        )
        new_token.value = _addr(handle)
        return int(ok)

    def set_entries_in_acl_w(self, count: int, entries: Any, old_acl: Any, new_acl: ctypes.c_void_p) -> int:
        return int(self._SetEntriesInAclW(count, entries, old_acl, ctypes.byref(new_acl)))

    def set_named_security_info_w(
        self,
        path: str,
        object_type: int,
        information: int,
        _owner: None,
        _group: None,
        dacl: Any,
        _sacl: None,
    ) -> int:
        return int(self._SetNamedSecurityInfoW(path, object_type, information, None, None, dacl, None))

    def get_named_security_info_w(
        self,
        path: str,
        object_type: int,
        information: int,
        owner: ctypes.c_void_p,
        group: ctypes.c_void_p,
        dacl: ctypes.c_void_p,
        sacl: ctypes.c_void_p,
        descriptor: ctypes.c_void_p,
    ) -> int:
        return int(
            self._GetNamedSecurityInfoW(
                path,
                object_type,
                information,
                ctypes.byref(owner),
                ctypes.byref(group),
                ctypes.byref(dacl),
                ctypes.byref(sacl),
                ctypes.byref(descriptor),
            )
        )

    def get_temp_path_w(self, length: int, buffer: Any) -> int:
        return int(self._GetTempPathW(length, buffer))

    def create_file_w(
        self,
        file_name: str,
        desired_access: int,
        share_mode: int,
        _attributes: None,
        creation: int,
        flags: int,
        _template: None,
    ) -> int | None:
        handle = self._CreateFileW(file_name, desired_access, share_mode, None, creation, flags, None)
        return None if is_invalid_handle(handle) else _addr(handle)

    def lock_file_ex(self, file: Any, flags: int, reserved: int, low: int, high: int, overlapped: Any) -> int:
        return int(self._LockFileEx(file, flags, reserved, low, high, ctypes.byref(overlapped)))

    def unlock_file_ex(self, file: Any, reserved: int, low: int, high: int, overlapped: Any) -> int:
        return int(self._UnlockFileEx(file, reserved, low, high, ctypes.byref(overlapped)))

    def create_pipe(self, read_slot: ctypes.c_void_p, write_slot: ctypes.c_void_p, _attributes: None, size: int) -> int:
        read = wintypes.HANDLE()
        write = wintypes.HANDLE()
        ok = self._CreatePipe(ctypes.byref(read), ctypes.byref(write), None, size)
        read_slot.value = _addr(read)
        write_slot.value = _addr(write)
        return int(ok)

    def set_handle_information(self, handle: Any, mask: int, flags: int) -> int:
        return int(self._SetHandleInformation(handle, mask, flags))

    def create_process_as_user_w(
        self,
        token: Any,
        _application: None,
        command_line: str,
        _process_attr: None,
        _thread_attr: None,
        inherit: int,
        creation_flags: int,
        _environment: None,
        cwd: str | None,
        startup: STARTUPINFOW,
        process_info: PROCESS_INFORMATION,
    ) -> int:
        mutable = ctypes.create_unicode_buffer(command_line)
        return int(
            self._CreateProcessAsUserW(
                token,
                None,
                mutable,
                None,
                None,
                inherit,
                creation_flags,
                None,
                cwd,
                ctypes.byref(startup),
                ctypes.byref(process_info),
            )
        )

    def set_environment_variable_w(self, name: str, value: str) -> int:
        return int(self._SetEnvironmentVariableW(name, value))

    def read_file(self, file: Any, buffer: Any, count: int, bytes_read: ctypes.c_uint32, _overlapped: None) -> int:
        return int(self._ReadFile(file, buffer, count, ctypes.byref(bytes_read), None))

    def peek_named_pipe(
        self,
        pipe: Any,
        _buffer: None,
        size: int,
        bytes_read: ctypes.c_uint32,
        total_avail: ctypes.c_uint32,
        left: ctypes.c_uint32,
    ) -> int:
        return int(
            self._PeekNamedPipe(
                pipe,
                None,
                size,
                ctypes.byref(bytes_read),
                ctypes.byref(total_avail),
                ctypes.byref(left),
            )
        )

    def wait_for_single_object(self, handle: Any, milliseconds: int) -> int:
        return int(self._WaitForSingleObject(handle, milliseconds))

    def get_exit_code_process(self, process: Any, exit_code: ctypes.c_uint32) -> int:
        return int(self._GetExitCodeProcess(process, ctypes.byref(exit_code)))

    def resume_thread(self, thread: Any) -> int:
        return int(self._ResumeThread(thread))

    def create_job_object_w(self, _attributes: None, _name: None) -> int | None:
        handle = self._CreateJobObjectW(None, None)
        return None if is_null_ptr(handle) else _addr(handle)

    def set_information_job_object(self, job: Any, cls: int, information: Any, length: int) -> int:
        return int(self._SetInformationJobObject(job, cls, information, length))

    def assign_process_to_job_object(self, job: Any, process: Any) -> int:
        return int(self._AssignProcessToJobObject(job, process))

    def terminate_process(self, process: Any, exit_code: int) -> int:
        return int(self._TerminateProcess(process, exit_code))

    def set_console_ctrl_handler(self, _handler: None, add: int) -> int:
        return int(self._SetConsoleCtrlHandler(None, add))

    def get_std_handle(self, std_handle: int) -> int | None:
        handle = self._GetStdHandle(std_handle)
        return None if is_null_ptr(handle) else _addr(handle)


_cached: Win32Bindings | None = None


def alloc_bytes(api: Win32Bindings, length: int) -> int:
    ptr = api.local_alloc(LMEM_ZEROINIT, length)
    if ptr is None:
        throw_last_error(api, "LocalAlloc", f"{length} bytes")
    return ptr


def win32_sync() -> Win32Bindings:
    global _cached
    if _cached is None:
        _cached = Win32Bindings()
    return _cached


def error_text(api: Win32Bindings, win32_code: int) -> str:
    buffer = ctypes.create_unicode_buffer(1024)
    length = api.format_message_w(
        FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        None,
        win32_code,
        0,
        buffer,
        1024,
        None,
    )
    if length == 0:
        return ""
    return buffer.value.strip()


def get_temp_path(api: Win32Bindings) -> str:
    buffer = ctypes.create_unicode_buffer(MAX_PATH + 1)
    length = api.get_temp_path_w(MAX_PATH + 1, buffer)
    if length == 0:
        throw_last_error(api, "GetTempPathW")
    if length > MAX_PATH + 1:
        raise Win32Error(
            "GetTempPathW",
            ERROR_INSUFFICIENT_BUFFER,
            f"required {length} chars exceed the {MAX_PATH + 1}-char buffer; nothing was written",
        )
    return buffer.value


def throw_last_error(api: Win32Bindings, name: str, detail: str | None = None) -> None:
    code = api.get_last_error()
    raise Win32Error(name, code, detail if detail is not None else error_text(api, code))


def throw_win32(api: Win32Bindings, name: str, win32_code: int, detail: str | None = None) -> None:
    raise Win32Error(name, win32_code, detail if detail is not None else error_text(api, win32_code))
