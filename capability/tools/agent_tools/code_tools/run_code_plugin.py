# -*- coding: utf-8 -*-
"""Execute a Python program that calls the other agent tools."""

from __future__ import annotations

import importlib.util
import json
import sys
import textwrap
import threading
from pathlib import Path
from typing import Any, Callable, Optional


PLUGIN_NAME = "run_code"
PLUGIN_VERSION = "1.0"

DEFAULT_TIMEOUT_MS = 60_000
_SAFE_BUILTIN_NAMES = (
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "filter",
    "float",
    "int",
    "isinstance",
    "len",
    "list",
    "map",
    "max",
    "min",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
    "Exception",
    "IndexError",
    "KeyError",
    "RuntimeError",
    "StopIteration",
    "TypeError",
    "ValueError",
)

RUN_CODE_SCHEMA: dict[str, Any] = {
    "name": "run_code",
    "description": (
        "Execute a Python program against the available tools. Takes two required "
        "arguments: `code`, the body of a function (`return` works), and "
        "`description`, a short summary of what the program does. Call tools as "
        "`tools.name({...})`. Answer with `print(...)` and/or `return <value>` — "
        "only that comes back, so curate it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The program: the body of a Python function.",
            },
            "description": {
                "type": "string",
                "description": (
                    "Clear, concise description of what this program does in "
                    "active voice, 5-10 words (shown in the UI)."
                ),
            },
            "timeoutMs": {
                "type": "number",
                "description": "Timeout in milliseconds. Defaults to 60000.",
            },
        },
        "required": ["code", "description"],
    },
}


def tool_schemas() -> list[dict[str, Any]]:
    return [RUN_CODE_SCHEMA]


def load(kind, body, call_params=None):
    """Load one tool call. Argument shape stays in this plugin."""
    if kind != "tool":
        raise ValueError(f"This process cannot load {kind}")
    if not isinstance(body, dict):
        raise TypeError("tool content must be a mapping")
    return dispatch("run_code", body, **(call_params or {}))


def dispatch(name: str, arguments: dict[str, Any], **kwargs: Any) -> str:
    if name != "run_code":
        return _error(f"unknown tool: {name}")
    kwargs.pop("mode", None)
    return run_code(
        code=str(arguments.get("code") or ""),
        description=str(arguments.get("description") or ""),
        timeout_ms=arguments.get("timeoutMs"),
        **kwargs,
    )


def run_code(
    code: str,
    description: str,
    timeout_ms: Optional[float] = None,
    workspace: Optional[str] = None,
    tool_caller: Optional[Callable[..., Any]] = None,
) -> str:
    """Run `code` and return its prints plus the JSON return value."""
    if not code.strip():
        return _error("invalid code: expected a non-empty string")
    if not description.strip():
        return _error("invalid description: expected a non-empty string")
    if timeout_ms is not None and (not isinstance(timeout_ms, (int, float)) or timeout_ms <= 0):
        return _error(f"invalid timeoutMs: expected a positive number, got {timeout_ms!r}")

    timeout = (timeout_ms or DEFAULT_TIMEOUT_MS) / 1000.0
    tools = _ToolNamespace(workspace, tool_caller or _call_plugin)
    try:
        logs, result = _run_with_timeout(lambda: _execute(code, tools), timeout)
    except TimeoutError:
        return _error(f"program timed out after {int(timeout * 1000)}ms")
    except Exception as exc:
        return _error(str(exc))
    try:
        encoded = json.loads(json.dumps(result, ensure_ascii=False))
    except TypeError as exc:
        return _error(f"return value must be JSON: {exc}")
    return json.dumps(
        {"success": True, "logs": logs, "result": encoded},
        ensure_ascii=False,
    )


class _ToolNamespace:
    """`tools.name(arguments)` loads that agent tool and returns its JSON."""

    def __init__(self, workspace: Optional[str], caller: Callable[..., Any]) -> None:
        self._workspace = workspace
        self._caller = caller

    def __getattr__(self, name: str):
        if name.startswith("_") or name == "run_code":
            raise AttributeError("run_code cannot call itself")

        def call(arguments: Any = None, **kwargs: Any) -> Any:
            if arguments is not None and not isinstance(arguments, dict):
                raise TypeError("tool arguments must be an object")
            payload = dict(arguments or {})
            payload.update(kwargs)
            raw = self._caller(name, payload, workspace=self._workspace)
            if not isinstance(raw, str):
                return raw
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw

        return call


def _execute(code: str, tools: _ToolNamespace) -> tuple[list[str], Any]:
    logs: list[str] = []

    def _print(*args: Any, sep: str = " ", end: str = "\n", **_kwargs: Any) -> None:
        text = sep.join(str(arg) for arg in args)
        if end:
            text += end
        logs.append(text.rstrip("\n"))

    source = "def _program():\n" + textwrap.indent(code, "    ") + "\n"
    try:
        compiled = compile(source, "<run_code>", "exec")
    except SyntaxError as exc:
        raise RuntimeError(f"invalid code: {exc.msg}") from exc
    namespace: dict[str, Any] = {
        "__builtins__": _safe_builtins(),
        "json": json,
        "print": _print,
        "tools": tools,
    }
    exec(compiled, namespace, namespace)
    return logs, namespace["_program"]()


def _safe_builtins() -> dict[str, Any]:
    source = __builtins__ if isinstance(__builtins__, dict) else __builtins__.__dict__
    return {name: source[name] for name in _SAFE_BUILTIN_NAMES if name in source}


def _run_with_timeout(fn: Callable[[], Any], timeout: float) -> Any:
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = fn()
        except Exception as exc:
            box["error"] = exc

    thread = threading.Thread(target=target, name="run-code", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError(timeout)
    if "error" in box:
        raise box["error"]
    return box["value"]


def _call_plugin(name: str, arguments: dict[str, Any], workspace: Optional[str] = None) -> str:
    path = _plugin_path(name)
    if path is None:
        raise RuntimeError(f"unknown tool: {name}")
    module = _load_module(path)
    dispatch = getattr(module, "dispatch", None)
    if not callable(dispatch):
        raise RuntimeError(f"unknown tool: {name}")
    return dispatch(name, arguments, workspace=workspace)


def _plugin_path(name: str) -> Path | None:
    root = Path(__file__).resolve().parents[1]
    matches = [
        path
        for path in root.rglob(f"{name}_plugin.py")
        if path.is_file() and path.name != "run_code_plugin.py"
    ]
    if not matches:
        return None
    matches.sort(key=lambda path: (len(path.parts), str(path)))
    return matches[0]


def _load_module(path: Path):
    module_name = f"linope_agent_tool_{path.stem}"
    cached = sys.modules.get(module_name)
    if cached is not None and getattr(cached, "__file__", None) == str(path):
        return cached
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _error(message: str, **details: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)


def capability_profile(capability_id, changes):
    """This process leases a tool and the shared project workspace."""
    from kernel.process.profiles import tool_with_workspace

    return tool_with_workspace(capability_id, changes)
