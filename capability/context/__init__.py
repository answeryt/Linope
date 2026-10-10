"""Context capability package. Its load chooses the compression function."""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Any


def load_in_directory(directory: Path, kind: str, body: Any) -> Any:
    """Load context content with the one function in this folder that fits."""
    if kind != "context":
        raise ValueError(f"这个进程不能装入 {kind}")
    arguments = _arguments(body)
    matches = _functions_for_arguments(directory, arguments)
    if len(matches) != 1:
        raise ValueError(
            "没有能装入这份内容的函数" if not matches else "这份内容对应不止一个函数"
        )
    return _invoke(matches[0], arguments)


def _arguments(body: Any) -> dict[str, Any]:
    if isinstance(body, dict):
        return body
    if isinstance(body, str):
        return {"messages": [{"role": "user", "content": body}]}
    raise TypeError("context 的内容必须是映射或文本")


def _functions_for_arguments(directory: Path, arguments: dict[str, Any]) -> list[Any]:
    keys = set(arguments)
    found: list[Any] = []
    seen: set[int] = set()
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("test_") or path.name == "__init__.py":
            continue
        module = _load(path)
        for name, value in vars(module).items():
            if not _is_local_function(name, value, directory) or id(value) in seen:
                continue
            if not _accepts_arguments(value, keys):
                continue
            seen.add(id(value))
            found.append(value)
    return found


def _is_local_function(name: str, value: Any, directory: Path) -> bool:
    if not inspect.isfunction(value) or name.startswith("_") or name in {
        "capability_profile",
        "load",
    }:
        return False
    code = getattr(value, "__code__", None)
    if code is None:
        return False
    return Path(code.co_filename).resolve().parent == directory.resolve()


def _accepts_arguments(function: Any, keys: set[str]) -> bool:
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return False
    required: set[str] = set()
    accepted: set[str] = set()
    for parameter in signature.parameters.values():
        if parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue
        accepted.add(parameter.name)
        if parameter.default is inspect.Parameter.empty:
            required.add(parameter.name)
    return required <= keys <= accepted


def _invoke(function: Any, arguments: dict[str, Any]) -> Any:
    try:
        bound = inspect.signature(function).bind(**arguments)
    except TypeError as error:
        raise TypeError(f"不能装入内容: {error}") from error
    bound.apply_defaults()
    if inspect.iscoroutinefunction(function):
        return __import__("asyncio").run(function(*bound.args, **bound.kwargs))
    return function(*bound.args, **bound.kwargs)


def _load(path: Path) -> Any:
    resolved = path.resolve()
    for module in list(sys.modules.values()):
        raw = getattr(module, "__file__", None)
        if raw and Path(raw).resolve() == resolved:
            return module
    token = "".join(character if character.isalnum() else "_" for character in resolved.as_posix())
    name = "context_capability_" + token[-80:]
    spec = importlib.util.spec_from_file_location(name, resolved)
    if spec is None or spec.loader is None:
        raise ImportError(resolved)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
