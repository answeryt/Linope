# -*- coding: utf-8 -*-
"""Spawn under a restricted token. quote_arg is host-independent."""

from __future__ import annotations

import re
import time
from collections.abc import Sequence
from typing import Any


PLUGIN_NAME = "sandbox_windows_acl_spawn"
PLUGIN_VERSION = "1.0"

HANDLE_FLAG_INHERIT = 0x1
STARTF_USESTDHANDLES = 0x00000100
STARTUPINFOW_SIZE = 104
CREATE_SUSPENDED = 0x4
STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11
STD_ERROR_HANDLE = -12
INFINITE = 0xFFFFFFFF
ERROR_BROKEN_PIPE = 109
ERROR_NO_DATA = 232
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOBOBJECT_EXTENDED_LIMIT_SIZE = 144
JOBOBJECT_EXTENDED_LIMIT_FLAGS_OFFSET = 16


def quote_arg(argument: str) -> str:
    if argument == "":
        return '""'
    if not re.search(r'[\s"]', argument):
        return argument
    quoted = '"'
    index = 0
    length = len(argument)
    while index < length:
        backslashes = 0
        while index < length and argument[index] == "\\":
            backslashes += 1
            index += 1
        if index == length:
            quoted += "\\" * (backslashes * 2)
        elif argument[index] == '"':
            quoted += "\\" * (backslashes * 2 + 1) + '"'
            index += 1
        else:
            quoted += "\\" * backslashes + argument[index]
            index += 1
    return quoted + '"'


def build_command_line(program: str, args: Sequence[str]) -> str:
    return " ".join(quote_arg(item) for item in (program, *args))


def _create_pipe(api: Any, ffi: Any) -> tuple[Any, Any]:
    read_slot = ffi.alloc_ptr_slot()
    write_slot = ffi.alloc_ptr_slot()
    if api.create_pipe(read_slot, write_slot, None, 0) == 0:
        ffi.throw_last_error(api, "CreatePipe")
    read = ffi.decode_ptr(read_slot)
    write = ffi.decode_ptr(write_slot)
    if read is None or write is None:
        ffi.throw_last_error(api, "CreatePipe", "null pipe handle")
    return read, write


def _set_inheritable(api: Any, handle: Any, label: str, ffi: Any) -> None:
    if api.set_handle_information(handle, HANDLE_FLAG_INHERIT, HANDLE_FLAG_INHERIT) == 0:
        ffi.throw_last_error(api, "SetHandleInformation", label)


def spawn_sandboxed(api: Any, token: Any, options: dict[str, Any], ffi: Any) -> dict[str, Any]:
    stdin_r, stdin_w = _create_pipe(api, ffi)
    stdout_r, stdout_w = _create_pipe(api, ffi)
    stderr_r, stderr_w = _create_pipe(api, ffi)
    _set_inheritable(api, stdin_r, "stdin read end", ffi)
    _set_inheritable(api, stdout_w, "stdout write end", ffi)
    _set_inheritable(api, stderr_w, "stderr write end", ffi)
    startup = ffi.alloc_startup_info()
    ffi.encode_startup_info(
        startup,
        {
            "cb": STARTUPINFOW_SIZE,
            "dwFlags": STARTF_USESTDHANDLES,
            "hStdInput": stdin_r,
            "hStdOutput": stdout_w,
            "hStdError": stderr_w,
        },
    )
    process_info = ffi.alloc_process_info()
    command_line = build_command_line(options["command"], list(options.get("args") or ()))
    created = api.create_process_as_user_w(
        token,
        None,
        command_line,
        None,
        None,
        1,
        0,
        None,
        options["cwd"],
        startup,
        process_info,
    )
    if created == 0:
        code = api.get_last_error()
        for handle in (stdin_r, stdin_w, stdout_r, stdout_w, stderr_r, stderr_w):
            api.close_handle(handle)
        ffi.throw_win32(
            api,
            "CreateProcessAsUserW",
            code,
            f"command: {options['command']}, cwd: {options['cwd']}",
        )
    info = ffi.decode_process_info(process_info)
    process_handle = info["hProcess"]
    thread_handle = info["hThread"]
    if process_handle is None or thread_handle is None:
        raise RuntimeError(
            f"CreateProcessAsUserW succeeded but returned null process/thread handles (pid {info['dwProcessId']})"
        )
    api.close_handle(stdin_r)
    api.close_handle(stdout_w)
    api.close_handle(stderr_w)
    api.close_handle(stdin_w)
    api.close_handle(thread_handle)
    return {
        "pid": info["dwProcessId"],
        "process": process_handle,
        "stdoutRead": stdout_r,
        "stderrRead": stderr_r,
    }


def drain_pipe(api: Any, handle: Any, ffi: Any) -> bytes:
    chunks: list[bytes] = []
    while True:
        bytes_read = ffi.alloc_uint32()
        total_avail = ffi.alloc_uint32()
        left = ffi.alloc_uint32()
        peeked = api.peek_named_pipe(handle, None, 0, bytes_read, total_avail, left)
        if peeked == 0:
            code = api.get_last_error()
            if code in {ERROR_BROKEN_PIPE, ERROR_NO_DATA}:
                break
            ffi.throw_last_error(api, "PeekNamedPipe", f"drain failure after {len(chunks)} chunk(s)")
        available = ffi.decode_uint32(total_avail)
        if available > 0:
            import ctypes

            chunk = (ctypes.c_ubyte * available)()
            read_slot = ffi.alloc_uint32()
            if api.read_file(handle, chunk, available, read_slot, None) == 0:
                ffi.throw_last_error(api, "ReadFile", f"drain failure after {len(chunks)} chunk(s)")
            chunks.append(bytes(chunk[: ffi.decode_uint32(read_slot)]))
        time.sleep(0.001)
    api.close_handle(handle)
    return b"".join(chunks)


def wait_for_exit(api: Any, process: Any, ffi: Any) -> int:
    waited = api.wait_for_single_object(process, INFINITE)
    if waited == 0xFFFFFFFF:
        ffi.throw_last_error(api, "WaitForSingleObject")
    exit_code = ffi.alloc_uint32()
    if api.get_exit_code_process(process, exit_code) == 0:
        ffi.throw_last_error(api, "GetExitCodeProcess")
    api.close_handle(process)
    return ffi.decode_uint32(exit_code)


def _create_kill_on_close_job(api: Any, ffi: Any) -> Any:
    job = api.create_job_object_w(None, None)
    if ffi.is_null_ptr(job):
        ffi.throw_last_error(api, "CreateJobObjectW")
    information = bytearray(JOBOBJECT_EXTENDED_LIMIT_SIZE)
    information[JOBOBJECT_EXTENDED_LIMIT_FLAGS_OFFSET:JOBOBJECT_EXTENDED_LIMIT_FLAGS_OFFSET + 4] = (
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ).to_bytes(4, "little")
    if api.set_information_job_object(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, bytes(information), len(information)) == 0:
        code = api.get_last_error()
        api.close_handle(job)
        ffi.throw_win32(api, "SetInformationJobObject", code)
    return job


def spawn_sandboxed_inherited(api: Any, token: Any, options: dict[str, Any], ffi: Any) -> dict[str, Any]:
    job = _create_kill_on_close_job(api, ffi)
    stdin = api.get_std_handle(STD_INPUT_HANDLE)
    stdout = api.get_std_handle(STD_OUTPUT_HANDLE)
    stderr = api.get_std_handle(STD_ERROR_HANDLE)
    if ffi.is_null_ptr(stdin) or ffi.is_null_ptr(stdout) or ffi.is_null_ptr(stderr):
        api.close_handle(job)
        ffi.throw_last_error(api, "GetStdHandle", "null standard handle")
    for handle, label in ((stdin, "stdin"), (stdout, "stdout"), (stderr, "stderr")):
        _set_inheritable(api, handle, f"{label} (enable inherit)", ffi)
    startup = ffi.alloc_startup_info()
    ffi.encode_startup_info(
        startup,
        {
            "cb": STARTUPINFOW_SIZE,
            "dwFlags": STARTF_USESTDHANDLES,
            "hStdInput": stdin,
            "hStdOutput": stdout,
            "hStdError": stderr,
        },
    )
    process_info = ffi.alloc_process_info()
    command_line = build_command_line(options["command"], list(options.get("args") or ()))
    created = api.create_process_as_user_w(
        token,
        None,
        command_line,
        None,
        None,
        1,
        CREATE_SUSPENDED,
        None,
        options["cwd"],
        startup,
        process_info,
    )
    for handle in (stdin, stdout, stderr):
        api.set_handle_information(handle, HANDLE_FLAG_INHERIT, 0)
    if created == 0:
        code = api.get_last_error()
        api.close_handle(job)
        ffi.throw_win32(
            api,
            "CreateProcessAsUserW",
            code,
            f"command: {options['command']}, cwd: {options['cwd']}",
        )
    info = ffi.decode_process_info(process_info)
    process_handle = info["hProcess"]
    thread_handle = info["hThread"]
    if process_handle is None or thread_handle is None:
        api.close_handle(job)
        raise RuntimeError(
            f"CreateProcessAsUserW succeeded but returned null process/thread handles (pid {info['dwProcessId']})"
        )
    if api.assign_process_to_job_object(job, process_handle) == 0:
        code = api.get_last_error()
        api.terminate_process(process_handle, 1)
        api.close_handle(thread_handle)
        api.close_handle(process_handle)
        api.close_handle(job)
        ffi.throw_win32(api, "AssignProcessToJobObject", code, f"pid {info['dwProcessId']}")
    if api.resume_thread(thread_handle) == 0xFFFFFFFF:
        code = api.get_last_error()
        api.close_handle(thread_handle)
        api.close_handle(process_handle)
        api.close_handle(job)
        ffi.throw_win32(api, "ResumeThread", code, f"pid {info['dwProcessId']}")
    api.close_handle(thread_handle)
    return {"pid": info["dwProcessId"], "process": process_handle, "job": job}
