# -*- coding: utf-8 -*-
"""Windows ACL confine runner. Loads sibling plugins by path; never imports them."""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


PLUGIN_NAME = "sandbox_windows_acl_runner"
PLUGIN_VERSION = "1.0"

RUNNER_SIGNATURE = "windows-acl-run"
RUNNER_FAILURE_EXIT = 127
READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"


class RunnerFailure(Exception):
    """Printed as windows-acl-run: <detail> and mapped to exit 127."""


def fail(detail: str) -> None:
    sys.stderr.write(f"{RUNNER_SIGNATURE}: {detail}\n")
    raise RunnerFailure(detail)


def parse_args(raw: list[str]) -> dict[str, Any]:
    workspace = None
    temp = None
    mode = None
    write_sid = None
    temp_write_sid = None
    index = 0
    while index < len(raw):
        token = raw[index]
        if token == "--":
            index += 1
            break
        index += 1
        if index >= len(raw):
            fail(f"missing value after {token}")
        value = raw[index]
        if token == "--workspace":
            workspace = value
        elif token == "--temp":
            temp = value
        elif token == "--mode":
            mode = value
        elif token == "--write-sid":
            write_sid = value
        elif token == "--temp-write-sid":
            temp_write_sid = value
        else:
            fail(f"unknown argument: {token}")
        index += 1
    if workspace is None:
        fail("missing --workspace")
    if temp is None:
        fail("missing --temp")
    if mode not in {READ_ONLY, WORKSPACE_WRITE}:
        fail(f"unknown mode: {mode}")
    argv = raw[index:]
    if not argv:
        fail("missing command after --")
    return {
        "workspace": workspace,
        "temp": temp,
        "mode": mode,
        "write_sid": write_sid,
        "temp_write_sid": temp_write_sid,
        "command": argv[0],
        "args": argv[1:],
    }


def require_directory(label: str, path: str) -> None:
    if not os.path.isdir(path):
        fail(f"{label} is not an existing directory: {path}")


def _load(name: str, filename: str) -> Any:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wire_sandbox(options: dict[str, Any]) -> Any:
    ffi = _load("sandbox_windows_acl_ffi", "ffi_plugin.py")
    acl = _load("sandbox_windows_acl_acl", "acl_plugin.py")
    token = _load("sandbox_windows_acl_token", "token_plugin.py")
    spawn = _load("sandbox_windows_acl_spawn", "spawn_plugin.py")
    boundary = _load("sandbox_windows_acl_path_boundary", "path_boundary_plugin.py")
    sandbox = _load("sandbox_windows_acl", "windows_acl_plugin.py")
    return sandbox.build_sandbox(
        options,
        ffi=ffi,
        grant_write=acl.grant_write,
        revoke_write=acl.revoke_write,
        open_current_process_token=token.open_current_process_token,
        find_logon_sid=token.find_logon_sid,
        make_well_known_sid=token.make_well_known_sid,
        create_restricted_token=token.create_restricted_token,
        set_token_default_dacl_grant=token.set_token_default_dacl_grant,
        build_explicit_access=acl.build_explicit_access,
        assert_private_temp_disjoint=boundary.assert_private_temp_disjoint,
        spawn_sandboxed=spawn.spawn_sandboxed,
        spawn_sandboxed_inherited=spawn.spawn_sandboxed_inherited,
        drain_pipe=spawn.drain_pipe,
        wait_for_exit=spawn.wait_for_exit,
    )


def run(argv: list[str] | None = None) -> int:
    parsed = parse_args(list(argv if argv is not None else sys.argv[1:]))
    require_directory("--workspace", parsed["workspace"])
    require_directory("--temp", parsed["temp"])
    seam_managed = parsed["write_sid"] is not None or parsed["temp_write_sid"] is not None
    if parsed["mode"] == READ_ONLY and seam_managed:
        fail("read-only does not accept --write-sid or --temp-write-sid")
    if parsed["mode"] == WORKSPACE_WRITE and (parsed["write_sid"] is None) != (parsed["temp_write_sid"] is None):
        fail("workspace-write requires --write-sid and --temp-write-sid together")
    sids = _load("sandbox_windows_acl_workspace_sid", "workspace_sid_plugin.py")
    boundary = _load("sandbox_windows_acl_path_boundary", "path_boundary_plugin.py")
    if parsed["mode"] == WORKSPACE_WRITE:
        boundary.assert_temp_root_outside_workspace(parsed["workspace"], parsed["temp"])
    ffi = _load("sandbox_windows_acl_ffi", "ffi_plugin.py")
    api = ffi.win32_sync()
    if api.set_console_ctrl_handler(None, 1) == 0:
        fail(f"SetConsoleCtrlHandler failed (Win32 {api.get_last_error()})")
    owned_temp = None
    sandbox = None
    initialized = False
    try:
        private_temp = None
        write_sid = None
        private_temp_sid = None
        if parsed["mode"] == WORKSPACE_WRITE:
            write_sid = sids.workspace_write_sid(parsed["workspace"])
            if seam_managed:
                if parsed["write_sid"] != write_sid:
                    fail("--write-sid does not match --workspace")
                private_temp = parsed["temp"]
                private_temp_sid = sids.temp_write_sid(private_temp)
                if parsed["temp_write_sid"] != private_temp_sid:
                    fail("--temp-write-sid does not match --temp")
            else:
                owned_temp = tempfile.mkdtemp(prefix="ol-", dir=parsed["temp"])
                private_temp = owned_temp
                private_temp_sid = sids.temp_write_sid(private_temp)
        options: dict[str, Any] = {
            "writable_dirs": [parsed["workspace"]] if parsed["mode"] == WORKSPACE_WRITE else [],
            "temp_dir": private_temp,
            "mode": parsed["mode"],
            "manage_dacls": not seam_managed,
        }
        if write_sid is not None:
            options["write_sid"] = write_sid
        if private_temp_sid is not None:
            options["temp_write_sid"] = private_temp_sid
        sandbox = wire_sandbox(options)
        sandbox.init()
        initialized = True
        if private_temp is not None:
            if api.set_environment_variable_w("TMP", private_temp) == 0:
                fail(f"SetEnvironmentVariableW TMP failed (Win32 {api.get_last_error()})")
            if api.set_environment_variable_w("TEMP", private_temp) == 0:
                fail(f"SetEnvironmentVariableW TEMP failed (Win32 {api.get_last_error()})")
        child = sandbox.spawn(
            {
                "command": parsed["command"],
                "args": parsed["args"],
                "stdio": "inherit",
            }
        )
        return int(child["wait"]()["exitCode"])
    finally:
        if initialized:
            try:
                if sandbox is not None:
                    sandbox.dispose()
            except Exception as error:
                sys.stderr.write(f"{RUNNER_SIGNATURE}: cleanup: {error}\n")
        if owned_temp is not None:
            try:
                import shutil

                shutil.rmtree(owned_temp, ignore_errors=True)
            except Exception as error:
                sys.stderr.write(f"{RUNNER_SIGNATURE}: cleanup: {error}\n")


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except RunnerFailure:
        return RUNNER_FAILURE_EXIT
    except Exception as error:
        sys.stderr.write(f"{RUNNER_SIGNATURE}: {error}\n")
        return RUNNER_FAILURE_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
