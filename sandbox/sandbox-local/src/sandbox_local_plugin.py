# -*- coding: utf-8 -*-
"""Pick a same-world runner and wrap argv. Fail closed. Host injects profiles."""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any


PLUGIN_NAME = "sandbox_local"
PLUGIN_VERSION = "1.0"

READ_ONLY = "read-only"
WORKSPACE_WRITE = "workspace-write"
DANGER_FULL_ACCESS = "danger-full-access"
CONFINED_MODES = (READ_ONLY, WORKSPACE_WRITE)

SANDBOX_UNAVAILABLE = "SANDBOX_UNAVAILABLE"

PLATFORM_CHAINS = {
    "linux": ("bwrap", "landlock"),
    "darwin": ("seatbelt",),
    "win32": ("windows-acl",),
}

STATIC_ENFORCEMENT = {
    "bwrap": "full",
    "landlock": "full",
    "seatbelt": "full",
    "windows-acl": "partial",
}

DENIAL_SIGNATURES = {
    "bwrap": ("read-only file system",),
    "landlock": ("permission denied",),
    "seatbelt": ("operation not permitted",),
    "windows-acl": ("access is denied", "access to the path", "permission denied"),
    "runner_command": ("read-only file system", "permission denied"),
}

RUNNER_FAILURE_RULES = {
    "bwrap": ({"fatal_signatures": ("bwrap: ",)},),
    "landlock": (
        {
            "allowed_exit_codes": (125,),
            "fatal_signatures": ("landlock-run: ",),
            "informational_lines": ("landlock-run: partial enforcement (older Landlock ABI)",),
        },
    ),
    "seatbelt": ({"fatal_signatures": ("sandbox-exec: ",)},),
    "windows-acl": (
        {"allowed_exit_codes": (127,), "fatal_signatures": ("windows-acl-run: ",)},
    ),
}

_WINDOWS_RUNNER = (
    Path(__file__).resolve().parents[2] / "sandbox-windows-acl" / "src" / "runner_plugin.py"
)


class SandboxUnavailableError(Exception):
    def __init__(self, mode: str, detail: str | None = None) -> None:
        message = (
            f'sandbox mode "{mode}" is requested but no sandbox backend is usable on this host; '
            "refusing to run the command unconfined. Install bubblewrap or run a Landlock-enforcing "
            "kernel (Linux), ensure sandbox-exec is usable (macOS), or ensure the ACL "
            "restricted-token runner can start (Windows) — otherwise switch the consumer to "
            "danger-full-access."
        )
        if detail is not None:
            message = f"{message} Runner failure: {detail}"
        super().__init__(message)
        self.name = "SandboxUnavailableError"
        self.code = SANDBOX_UNAVAILABLE


class LocalSandbox:
    """Platform chain: Linux bwrap then Landlock; macOS Seatbelt; Windows ACL runner."""

    def __init__(
        self,
        *,
        bwrap_profile_args: Callable[[Mapping[str, Any]], list[str]],
        landlock_profile_args: Callable[[Mapping[str, Any]], list[str]],
        seatbelt_profile_args: Callable[..., list[str]],
        writable_roots: Callable[[Mapping[str, Any]], list[str]] | None = None,
        runner_command: Sequence[str] | None = None,
        runner_failure_signatures: Sequence[str] = (),
        probe_timeout_ms: int = 5000,
        platform: str | None = None,
    ) -> None:
        if (runner_command and not runner_failure_signatures) or (
            not runner_command and runner_failure_signatures
        ):
            raise ValueError("sandbox-local: runnerCommand and runnerFailureSignatures travel together")
        self.bwrap_profile_args = bwrap_profile_args
        self.landlock_profile_args = landlock_profile_args
        self.seatbelt_profile_args = seatbelt_profile_args
        self.writable_roots = writable_roots
        self.runner_command = list(runner_command) if runner_command else None
        self.runner_failure_signatures = list(runner_failure_signatures)
        self.probe_timeout_ms = probe_timeout_ms
        self.platform = platform or sys.platform
        self._selected: tuple[str, str] | str | None = None

    def confine(self, argv: Sequence[str], policy: Mapping[str, Any]) -> dict[str, Any]:
        mode = str(policy.get("mode") or "")
        if mode not in CONFINED_MODES:
            raise ValueError(
                f'sandbox confine rejects "{mode}"; skip confine under danger-full-access'
            )
        if self.runner_command is not None:
            wrapped = [*self.runner_command, *self.bwrap_profile_args(policy), "--", *argv]
            return _result(wrapped, "full", DENIAL_SIGNATURES["runner_command"], (
                {"fatal_signatures": tuple(self.runner_failure_signatures)},
            ))
        runner, enforcement = self._select(mode)
        prefix = self._runner_argv(runner, policy)
        return _result(
            [*prefix, "--", *argv],
            enforcement,
            DENIAL_SIGNATURES[runner],
            RUNNER_FAILURE_RULES[runner],
        )

    def _select(self, mode: str) -> tuple[str, str]:
        if self._selected is None:
            self._selected = self._chain_verdict()
        if self._selected == "unavailable":
            raise SandboxUnavailableError(mode)
        return self._selected

    def _chain_verdict(self) -> tuple[str, str] | str:
        chain = PLATFORM_CHAINS.get(self.platform, ())
        if not chain:
            return "unavailable"
        if len(chain) == 1:
            return (chain[0], STATIC_ENFORCEMENT[chain[0]])
        for runner in chain:
            enforcement = self._probe(runner)
            if enforcement != "unusable":
                return (runner, enforcement)
        return "unavailable"

    def _probe(self, runner: str) -> str:
        timeout = max(self.probe_timeout_ms / 1000, 0.1)
        if runner == "bwrap":
            return "full" if _probe_bwrap(timeout) else "unusable"
        if runner == "landlock":
            launcher = shutil.which("landlock-run")
            return "full" if launcher and _probe_cmd([launcher, "--", "true"], timeout) else "unusable"
        if runner == "seatbelt":
            return "full" if _probe_cmd(["sandbox-exec", "-p", "(version 1)\n(allow default)", "--", "true"], timeout) else "unusable"
        if runner == "windows-acl":
            if not _WINDOWS_RUNNER.is_file():
                return "unusable"
            return "partial" if _WINDOWS_RUNNER.is_file() else "unusable"
        return "unusable"

    def _runner_argv(self, runner: str, policy: Mapping[str, Any]) -> list[str]:
        if runner == "bwrap":
            return ["bwrap", *self.bwrap_profile_args(policy)]
        if runner == "landlock":
            launcher = shutil.which("landlock-run") or "landlock-run"
            return [launcher, *self.landlock_profile_args(policy)]
        if runner == "seatbelt":
            kwargs = {}
            if self.writable_roots is not None:
                kwargs["writable_roots"] = self.writable_roots
            return ["sandbox-exec", *self.seatbelt_profile_args(policy, **kwargs)]
        root = str(policy.get("workspace_root") or policy.get("workspaceRoot") or "")
        import tempfile

        return [
            sys.executable,
            str(_WINDOWS_RUNNER),
            "--workspace",
            root,
            "--temp",
            tempfile.gettempdir(),
            "--mode",
            str(policy.get("mode") or ""),
        ]


def build_local_sandbox(
    *,
    bwrap_profile_args: Callable[[Mapping[str, Any]], list[str]],
    landlock_profile_args: Callable[[Mapping[str, Any]], list[str]],
    seatbelt_profile_args: Callable[..., list[str]],
    writable_roots: Callable[[Mapping[str, Any]], list[str]] | None = None,
    runner_command: Sequence[str] | None = None,
    runner_failure_signatures: Sequence[str] = (),
    probe_timeout_ms: int = 5000,
    platform: str | None = None,
) -> LocalSandbox:
    return LocalSandbox(
        bwrap_profile_args=bwrap_profile_args,
        landlock_profile_args=landlock_profile_args,
        seatbelt_profile_args=seatbelt_profile_args,
        writable_roots=writable_roots,
        runner_command=runner_command,
        runner_failure_signatures=runner_failure_signatures,
        probe_timeout_ms=probe_timeout_ms,
        platform=platform,
    )


def _result(
    argv: Sequence[str],
    enforcement: str,
    denial: Sequence[str],
    rules: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "argv": list(argv),
        "enforcement": enforcement,
        "denial_signatures": list(denial),
        "runner_failure_rules": [dict(rule) for rule in rules],
    }


def _probe_bwrap(timeout: float) -> bool:
    return _probe_cmd(
        ["bwrap", "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--die-with-parent", "--", "true"],
        timeout,
    )


def _probe_cmd(argv: Sequence[str], timeout: float) -> bool:
    try:
        completed = subprocess.run(list(argv), timeout=timeout, check=False, capture_output=True)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0
