"""Answer the kernel's sandbox questions. The kernel does not load these files."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def main() -> None:
    """Read one JSON object from stdin and write one JSON value."""
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise SystemExit(str(exc)) from exc
    if not isinstance(payload, dict):
        raise SystemExit("sandbox gate expects one record")
    json.dump(_answer(payload), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def _answer(payload: dict[str, Any]) -> Any:
    operation = str(payload.get("op") or "")
    if operation == "vocabulary":
        modes = _load("sandbox_plugin.py")
        return {
            "read_only": modes.READ_ONLY,
            "workspace_write": modes.WORKSPACE_WRITE,
            "danger_full_access": modes.DANGER_FULL_ACCESS,
            "modes": list(modes.SANDBOX_MODES),
            "confined": list(modes.CONFINED_MODES),
        }
    if operation == "writable-roots":
        roots = _load("roots_plugin.py")
        policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else {}
        return roots.writable_roots(policy)
    if operation == "canonical-path":
        roots = _load("roots_plugin.py")
        return roots.canonical_path(str(payload.get("path") or ""))
    if operation == "confine":
        return _confine(payload)
    raise SystemExit(f"Unknown sandbox question: {operation}")


def _confine(payload: dict[str, Any]) -> dict[str, Any]:
    local = _load_path(
        Path(__file__).resolve().parent / "sandbox-local" / "src" / "sandbox_local_plugin.py"
    )
    roots = _load("roots_plugin.py")
    sandbox = local.LocalSandbox(
        bwrap_profile_args=lambda policy: [],
        landlock_profile_args=lambda policy: [],
        seatbelt_profile_args=lambda policy, **kwargs: [],
        writable_roots=roots.writable_roots,
    )
    try:
        return sandbox.confine(
            list(payload.get("argv") or ()),
            {
                "mode": str(payload.get("mode") or ""),
                "workspace_root": str(payload.get("workspace_root") or ""),
            },
        )
    except local.SandboxUnavailableError as exc:
        raise SystemExit(str(exc)) from exc


def _load(name: str) -> Any:
    return _load_path(Path(__file__).resolve().parent / "sandbox" / "src" / name)


def _load_path(path: Path) -> Any:
    module_name = f"linope_sandbox_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Cannot load sandbox file: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    main()
