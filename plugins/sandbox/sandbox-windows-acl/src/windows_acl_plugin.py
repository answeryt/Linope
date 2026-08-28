# -*- coding: utf-8 -*-
"""WRITE_RESTRICTED AclSandbox. Host injects ffi, token, acl, spawn, and path checks."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any


PLUGIN_NAME = "sandbox_windows_acl"
PLUGIN_VERSION = "1.0"

READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
WIN_WORLD_SID = 1


class AclSandbox:
    """One write-restricted instance: token + grants + spawn. Fail-closed."""

    def __init__(
        self,
        options: dict[str, Any],
        *,
        ffi: Any,
        grant_write: Callable[..., None],
        revoke_write: Callable[..., bool],
        open_current_process_token: Callable[..., Any],
        find_logon_sid: Callable[..., Any],
        make_well_known_sid: Callable[..., Any],
        create_restricted_token: Callable[..., Any],
        set_token_default_dacl_grant: Callable[..., None],
        build_explicit_access: Callable[..., bytes],
        assert_private_temp_disjoint: Callable[..., None],
        spawn_sandboxed: Callable[..., dict[str, Any]],
        spawn_sandboxed_inherited: Callable[..., dict[str, Any]],
        drain_pipe: Callable[..., bytes],
        wait_for_exit: Callable[..., int],
    ) -> None:
        self.mode = str(options["mode"])
        self._manage_dacls = bool(options.get("manage_dacls", options.get("manageDacls", True)))
        self._ffi = ffi
        self._grant_write = grant_write
        self._revoke_write = revoke_write
        self._open_current_process_token = open_current_process_token
        self._find_logon_sid = find_logon_sid
        self._make_well_known_sid = make_well_known_sid
        self._create_restricted_token = create_restricted_token
        self._set_token_default_dacl_grant = set_token_default_dacl_grant
        self._build_explicit_access = build_explicit_access
        self._assert_private_temp_disjoint = assert_private_temp_disjoint
        self._spawn_sandboxed = spawn_sandboxed
        self._spawn_sandboxed_inherited = spawn_sandboxed_inherited
        self._drain_pipe = drain_pipe
        self._wait_for_exit = wait_for_exit
        self.writable_dirs = [
            _require_dir(item)
            for item in options.get("writable_dirs") or options.get("writableDirs") or ()
        ]
        self._temp_supplied = "temp_dir" in options or "tempDir" in options
        self.temp_dir_option = options.get("temp_dir", options.get("tempDir"))
        self.write_sid = options.get("write_sid", options.get("writeSid"))
        self.temp_write_sid = options.get("temp_write_sid", options.get("tempWriteSid"))
        self._temp_dir: str | None = None
        self._api: Any = None
        self._token: Any = None
        self._write_sid_ptr: Any = None
        self._temp_write_sid_ptr: Any = None
        self._sid_allocations: list[Any] = []
        self._granted: list[dict[str, Any]] = []
        self._validate()

    @property
    def temp_dir(self) -> str | None:
        return self._temp_dir

    def _validate(self) -> None:
        if self.mode == WORKSPACE_WRITE and self.write_sid is None:
            raise ValueError(
                "AclSandbox workspace-write requires a write SID — derive it via workspace_write_sid()"
            )
        if self.mode == WORKSPACE_WRITE and not self._temp_supplied:
            raise ValueError(
                "AclSandbox workspace-write requires an explicit private temp directory or null"
            )
        if self.mode == READ_ONLY and self.temp_dir_option is not None:
            raise ValueError("AclSandbox read-only does not accept a temp directory")
        if self.mode == READ_ONLY and (self.write_sid is not None or self.temp_write_sid is not None):
            raise ValueError("AclSandbox read-only does not accept write SIDs")
        if self.mode == WORKSPACE_WRITE and self.temp_dir_option is not None and self.temp_write_sid is None:
            raise ValueError(
                "AclSandbox workspace-write with temp requires a temp write SID — derive it via temp_write_sid()"
            )
        if self.temp_dir_option is None and self.temp_write_sid is not None:
            raise ValueError("AclSandbox temp write SID requires a temp directory")
        if self.write_sid is not None and self.temp_write_sid == self.write_sid:
            raise ValueError("AclSandbox workspace and temp write SIDs must be distinct")

    def init(self) -> None:
        if self._api is not None:
            raise RuntimeError("AclSandbox is already initialized")
        ffi = self._ffi
        api = ffi.win32_sync()
        current = self._open_current_process_token(api, ffi)
        current_open = True
        restricted = None
        try:
            self._write_sid_ptr = None if self.write_sid is None else _parse_sid(api, ffi, self.write_sid)
            self._temp_write_sid_ptr = None if self.temp_write_sid is None else _parse_sid(api, ffi, self.temp_write_sid)
            temp_dir = None if self.mode == READ_ONLY or self.temp_dir_option is None else str(self.temp_dir_option)
            if temp_dir is not None:
                _require_dir(temp_dir)
                self._assert_private_temp_disjoint(self.writable_dirs, temp_dir)
            self._temp_dir = temp_dir
            if self._manage_dacls and self._write_sid_ptr is not None:
                for path in self.writable_dirs:
                    self._grant_write(api, path, self._write_sid_ptr, ffi)
                if temp_dir is not None and self._temp_write_sid_ptr is not None:
                    self._granted.append({"path": temp_dir, "sidPtr": self._temp_write_sid_ptr})
                    self._grant_write(api, temp_dir, self._temp_write_sid_ptr, ffi)
            logon = self._find_logon_sid(api, current, ffi)
            self._sid_allocations.append(logon)
            world = self._make_well_known_sid(api, WIN_WORLD_SID, ffi)
            self._sid_allocations.append(world)
            write_sids = [item for item in (self._write_sid_ptr, self._temp_write_sid_ptr) if item is not None]
            restricted = self._create_restricted_token(
                api, current, logon, write_sids, {"world": world}, self.mode, ffi
            )
            self._token = restricted
            self._set_token_default_dacl_grant(
                api,
                restricted,
                self._temp_write_sid_ptr or self._write_sid_ptr or world,
                ffi,
                build_explicit_access=self._build_explicit_access,
            )
            if api.close_handle(current) == 0:
                ffi.throw_last_error(api, "CloseHandle", "current process token")
            current_open = False
            self._api = api
        except Exception as error:
            failures: list[BaseException] = []
            if current_open and api.close_handle(current) == 0:
                failures.append(RuntimeError(f"CloseHandle current process token after init failure: {api.get_last_error()}"))
            if restricted is not None and api.close_handle(restricted) == 0:
                failures.append(RuntimeError(f"CloseHandle restricted token after init failure: {api.get_last_error()}"))
            for grant in self._granted:
                try:
                    self._revoke_write(api, grant["path"], grant["sidPtr"], ffi)
                except Exception as cleanup:
                    failures.append(cleanup)
            for label, sid_ptr in (("workspace write SID", self._write_sid_ptr), ("temp write SID", self._temp_write_sid_ptr)):
                _free_sid(api, ffi, sid_ptr, label, failures)
            for sid_ptr in list(self._sid_allocations):
                _free_sid(api, ffi, sid_ptr, "init SID allocation", failures)
            self._sid_allocations.clear()
            self._token = None
            self._write_sid_ptr = None
            self._temp_write_sid_ptr = None
            self._temp_dir = None
            self._granted = []
            if failures:
                wrapped = RuntimeError(
                    f"AclSandbox init failed and {len(failures)} cleanup operation(s) also failed"
                )
                wrapped.exceptions = [error, *failures]
                raise wrapped
            raise

    def spawn(self, options: dict[str, Any]) -> dict[str, Any]:
        api = self._api
        token = self._token
        if api is None or token is None:
            raise RuntimeError("AclSandbox is not initialized: call init() first")
        args = list(options.get("args") or ())
        cwd = str(options.get("cwd") or os.getcwd())
        ffi = self._ffi
        payload = {"command": options["command"], "args": args, "cwd": cwd}
        if options.get("stdio") == "inherit":
            native = self._spawn_sandboxed_inherited(api, token, payload, ffi)

            def _wait_inherit() -> dict[str, Any]:
                exit_code = self._wait_for_exit(api, native["process"], ffi)
                if api.close_handle(native["job"]) == 0:
                    ffi.throw_last_error(api, "CloseHandle", "kill-on-close job")
                return {"stdout": b"", "stderr": b"", "exitCode": exit_code}

            return {"pid": native["pid"], "wait": _wait_inherit}
        native = self._spawn_sandboxed(api, token, payload, ffi)

        def _wait_pipe() -> dict[str, Any]:
            stdout = self._drain_pipe(api, native["stdoutRead"], ffi)
            stderr = self._drain_pipe(api, native["stderrRead"], ffi)
            exit_code = self._wait_for_exit(api, native["process"], ffi)
            return {"stdout": stdout, "stderr": stderr, "exitCode": exit_code}

        return {"pid": native["pid"], "wait": _wait_pipe}

    def dispose(self) -> None:
        api = self._api
        if api is None:
            return
        ffi = self._ffi
        failures: list[BaseException] = []
        if self._manage_dacls:
            for grant in self._granted:
                try:
                    self._revoke_write(api, grant["path"], grant["sidPtr"], ffi)
                except Exception as error:
                    failures.append(error)
        for label, sid_ptr in (("workspace write SID", self._write_sid_ptr), ("temp write SID", self._temp_write_sid_ptr)):
            _free_sid(api, ffi, sid_ptr, label, failures)
        if self._token is not None:
            try:
                if api.close_handle(self._token) == 0:
                    ffi.throw_last_error(api, "CloseHandle", "restricted token")
            except Exception as error:
                failures.append(error)
        for sid_ptr in list(self._sid_allocations):
            _free_sid(api, ffi, sid_ptr, "init SID allocation", failures)
        self._sid_allocations.clear()
        self._api = None
        self._token = None
        self._write_sid_ptr = None
        self._temp_write_sid_ptr = None
        self._granted = []
        if failures:
            error = RuntimeError(f"AclSandbox dispose completed with {len(failures)} cleanup failure(s)")
            error.exceptions = failures
            raise error


def build_sandbox(options: dict[str, Any], **injected: Any) -> AclSandbox:
    """Host entry: wire ffi / token / acl / spawn / path-boundary into one instance."""
    return AclSandbox(options, **injected)


def _require_dir(path: str) -> str:
    absolute = os.path.abspath(path)
    if not os.path.isdir(absolute):
        raise ValueError(f"AclSandbox writable dir does not exist or is not a directory: {absolute}")
    return absolute


def _parse_sid(api: Any, ffi: Any, sid: str) -> Any:
    slot = ffi.alloc_ptr_slot()
    if api.convert_string_sid_to_sid_w(sid, slot) == 0:
        ffi.throw_last_error(api, "ConvertStringSidToSidW", sid)
    parsed = ffi.decode_ptr(slot)
    if parsed is None:
        raise RuntimeError(f"ConvertStringSidToSidW returned null SID for {sid}")
    return parsed


def _free_sid(api: Any, ffi: Any, sid_ptr: Any, label: str, failures: list[BaseException]) -> None:
    if sid_ptr is None:
        return
    try:
        freed = api.local_free(sid_ptr)
        if not ffi.is_null_ptr(freed):
            ffi.throw_last_error(api, "LocalFree", label)
    except Exception as error:
        failures.append(error)
